import httpx
import asyncio
from os import getenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import py_engine_interpretor as py_interp
import json

class NetworkConfig(BaseModel):
    name: str
    url: str

networks_import = getenv("NETWORKS", '[{"name":"Paris","url":"http://localhost:8001"},{"name":"Mariana","url":"http://localhost:8002"},{"name":"Moon","url":"http://localhost:8003"}]')
networks = [NetworkConfig(name=net["name"], url=net["url"]) for net in json.loads(networks_import)]

NUM_SHARES = 3
DEGREE = 1
MIN_QUORUM = DEGREE + 1  # Threshold k = 2 for (2, 3) scheme

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Persistent HTTP client for connection pooling and keep-alive
    app.state.client = httpx.AsyncClient(timeout=5.0)
    yield
    await app.state.client.aclose()

app = FastAPI(title="Distributed-KMS Orchestrator", lifespan=lifespan)

class SecretCreateRequest(BaseModel):
    id: str
    secret: str

@app.post("/create_secret")
async def create_secret(request: SecretCreateRequest):
    try:
        aes_bytes = list(bytes.fromhex(request.secret))
    except ValueError:
        raise HTTPException(status_code=400, detail="Secret must be a valid hex-encoded string")

    num_bytes = len(aes_bytes)
    if num_bytes == 0 or num_bytes > 32:
        raise HTTPException(status_code=400, detail="Secret must be between 1 and 32 bytes (up to 64 hex chars)")
    
    xs = list(range(1, NUM_SHARES + 1))
    
    try:
        all_ys = py_interp.evaluate_share_batch(xs, aes_bytes, num_bytes, DEGREE)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"C engine evaluation failed: {str(e)}")
    
    shares = [{"x": x, "y_arr": all_ys[idx]} for idx, x in enumerate(xs)]
    
    clt = getattr(app.state, "client", None)
    should_close = False
    if clt is None:
        clt = httpx.AsyncClient(timeout=5.0)
        should_close = True

    try:
        tsks = [
            clt.post(f"{net.url}/store_share", json={"id": request.id, "share": share})
            for share, net in zip(shares, networks)
        ]
        results = await asyncio.gather(*tsks, return_exceptions=True)
    finally:
        if should_close:
            await clt.aclose()

    # Enforce write quorum: at least MIN_QUORUM nodes must acknowledge write
    success_count = 0
    errors = []
    for net, res in zip(networks, results):
        if isinstance(res, Exception):
            errors.append(f"{net.name}: {type(res).__name__}")
        elif res.status_code == 200:
            success_count += 1
        else:
            errors.append(f"{net.name}: HTTP {res.status_code}")

    if success_count < MIN_QUORUM:
        raise HTTPException(
            status_code=502,
            detail=f"Write quorum failed: persisted on {success_count}/{len(networks)} nodes (minimum {MIN_QUORUM} required). Failures: {errors}"
        )
    
    return {
        "message": "Secret created and shares distributed successfully",
        "quorum_achieved": f"{success_count}/{len(networks)}"
    }

@app.get("/reconstruct_secret")
async def reconstruct_secret(secret_id: str):
    clt = getattr(app.state, "client", None)
    should_close = False
    if clt is None:
        clt = httpx.AsyncClient(timeout=5.0)
        should_close = True

    try:
        tsks = [
            clt.get(f"{net.url}/get_share", params={"id": secret_id})
            for net in networks
        ]
        res = await asyncio.gather(*tsks, return_exceptions=True)
    finally:
        if should_close:
            await clt.aclose()
    
    valid_shares = []
    seen_xs = set()
    for r in res:
        if isinstance(r, Exception) or r.status_code != 200:
            continue
        try:
            payload = r.json()
            share = payload.get("share")
            if not share or "x" not in share or "y_arr" not in share:
                continue
            if share["x"] in seen_xs:
                continue
            seen_xs.add(share["x"])
            valid_shares.append(share)
        except Exception:
            continue
    
    num_shares = len(valid_shares)
    if num_shares < MIN_QUORUM:
        raise HTTPException(
            status_code=404,
            detail=f"Quorum not reached: retrieved {num_shares} valid shares (minimum {MIN_QUORUM} required to reconstruct)"
        )
    
    num_bytes = len(valid_shares[0]["y_arr"])
    xs = [share["x"] for share in valid_shares]
    ys_matrix = [share["y_arr"] for share in valid_shares]

    try:
        rec_ints = py_interp.lagrange_interpolation_batch(xs, ys_matrix, num_shares, num_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Interpolation failure: {str(e)}")
    
    # Boundary check: GF(257) values must map to valid 8-bit bytes [0, 255]
    if any(b < 0 or b > 255 for b in rec_ints):
        raise HTTPException(
            status_code=500,
            detail="Secret reconstruction resulted in out-of-range byte values (tampered or corrupted shares)"
        )

    bytes_toret = bytes(rec_ints)
    return {"secret": bytes_toret.hex()}