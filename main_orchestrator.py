import ctypes
import httpx
import asyncio
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import py_engine_interpretor as py_interp

networks = {
    "Paris_testnet": "http://127.0.0.1:8001",
    "Mariana_trench_testnet": "http://127.0.0.1:8002",
    "Moon_base": "http://127.0.0.1:8003"
}

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
    coeffs = (ctypes.c_int * (DEGREE + 1))()
    shares = [{"x": i, "y_arr" : []} for i in range(1, NUM_SHARES + 1)]
    rand_bytes = os.urandom(DEGREE * len(aes_bytes))
    for byte in aes_bytes:
        coeffs = (ctypes.c_int * (DEGREE + 1))()
        for i in range(1, DEGREE + 1):
            coeffs[i] = rand_bytes[(i-1)*len(aes_bytes) + aes_bytes.index(byte)]
        coeffs[0] = byte
        for i in range(1, NUM_SHARES + 1):
            share = py_interp.Share()
            py_interp.evaluate_share(ctypes.byref(share), i, coeffs, DEGREE)
            shares[i-1]["y_arr"].append(share.y)
    
    async with httpx.AsyncClient() as clt:
        tsks = []
        for (net_name, net_url), share in zip(networks.items(), shares):
            tsks.append(clt.post(f"{net_url}/store_share", json={"id": request.id, "share": {"x": share["x"], "y_arr": share["y_arr"]}}))

        await asyncio.gather(*tsks, return_exceptions=True) 


@app.get("/reconstruct_secret")
async def reconstruct_secret(secret_id : str):
    async with httpx.AsyncClient() as clt:
        tsks = []
        for net_name, net_url in networks.items():
            tsks.append(clt.get(f"{net_url}/get_share", params={"id": secret_id}))

        res = await asyncio.gather(*tsks, return_exceptions=True)
    
    valid_shares = []
    for r in res:
        if isinstance(r, Exception):
            continue
        if r.status_code == 200:
            valid_shares.append(r.json()["share"])
    
    if len(valid_shares) < 2:
        raise HTTPException(status_code=400, detail="Not enough shares to reconstruct the secret")
    
    num_bytes = len(valid_shares[0]["y_arr"])
    rec_bytes = bytearray()

    for i in range(num_bytes):
        c_shares = (py_interp.Share * len(valid_shares))()
        for j, share in enumerate(valid_shares):
            c_shares[j] = py_interp.Share(x=share["x"], y=share["y_arr"][i])
        rec_byte = py_interp.lagrange_interpolation(0, c_shares, len(valid_shares))
        rec_bytes.append(rec_byte)

    return {"secret": rec_bytes.hex()}
