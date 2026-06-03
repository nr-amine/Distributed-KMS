import httpx
import asyncio
from os import getenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import py_engine_interpretor as py_interp
import json

class NetworkConfig(BaseModel):
    name: str
    url: str

networks_import = getenv("NETWORKS")
if not networks_import:
    raise ValueError("NETWORKS environment variable not set")

networks = [NetworkConfig(name=net["name"], url=net["url"]) for net in json.loads(networks_import)]

    

NUM_SHARES = 3
DEGREE = 1
P = 257



app = FastAPI()


class SecretCreateRequest(BaseModel):
    id: str
    secret: str

@app.post("/create_secret")
async def create_secret(request: SecretCreateRequest):
    aes_bytes = list(bytes.fromhex(request.secret))
    num_bytes = len(aes_bytes)
    if num_bytes > 32:
        raise HTTPException(status_code=400, detail="Secret too long, must be at most 32 bytes")
    
    xs = list(range(1, NUM_SHARES + 1))
    
    all_ys = py_interp.evaluate_share_batch(xs, aes_bytes, num_bytes, DEGREE)
    
    shares = [{"x": x, "y_arr": all_ys[idx]} for idx, x in enumerate(xs)]
    
    async with httpx.AsyncClient() as clt:
        tsks = []
        for share, net in zip(shares, networks):
            tsks.append(clt.post(f"{net.url}/store_share", json={"id": request.id, "share": share}))

        await asyncio.gather(*tsks, return_exceptions=True) 
    
    return {"message": "Secret created and shares distributed successfully"}


@app.get("/reconstruct_secret")
async def reconstruct_secret(secret_id : str):
    async with httpx.AsyncClient() as clt:
        tsks = []
        for net in networks:
            tsks.append(clt.get(f"{net.url}/get_share", params={"id": secret_id}))

        res = await asyncio.gather(*tsks, return_exceptions=True)
    
    valid_shares = []
    for r in res:
        if isinstance(r, Exception):
            continue
        if r.status_code == 200:
            valid_shares.append(r.json()["share"])
    
    num_shares = len(valid_shares)
    if num_shares < 2:
        raise HTTPException(status_code=400, detail="Not enough shares to reconstruct the secret")
    
    num_bytes = len(valid_shares[0]["y_arr"])
    xs = [share["x"] for share in valid_shares]
    ys_matrix = [share["y_arr"] for share in valid_shares]

    rec_ints = py_interp.lagrange_interpolation_batch(xs, ys_matrix, num_shares, num_bytes)
    
    bytes_toret = bytes([b for b in rec_ints])
    return {"secret": bytes_toret.hex()}