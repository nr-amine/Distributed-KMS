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
    num_bytes = len(aes_bytes)
    
    shares = [{"x": i, "y_arr" : []} for i in range(1, NUM_SHARES + 1)]
    
    for i in range(1, NUM_SHARES + 1):
        shares[i-1]["y_arr"] = py_interp.evaluate_share_batch(i, aes_bytes, num_bytes, DEGREE)
    
    async with httpx.AsyncClient() as clt:
        tsks = []
        for (net_name, net_url), share in zip(networks.items(), shares):
            tsks.append(clt.post(f"{net_url}/store_share", json={"id": request.id, "share": {"x": share["x"], "y_arr": share["y_arr"]}}))

        await asyncio.gather(*tsks, return_exceptions=True) 
    
    return {"message": "Secret created and shares distributed successfully"}


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
    
    num_shares = len(valid_shares)
    if num_shares < 2:
        raise HTTPException(status_code=400, detail="Not enough shares to reconstruct the secret")
    
    num_bytes = len(valid_shares[0]["y_arr"])
    
    xs = [share["x"] for share in valid_shares]
    ys_matrix = [share["y_arr"] for share in valid_shares]

    rec_ints = py_interp.lagrange_interpolation_batch(xs, ys_matrix, num_shares, num_bytes)
    
    return {"secret": bytearray(rec_ints).hex()}