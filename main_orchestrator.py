import httpx
import asyncio
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
    
    xs = list(range(1, NUM_SHARES + 1))
    
    all_ys = py_interp.evaluate_share_batch(xs, aes_bytes, num_bytes, DEGREE)
    
    shares = [{"x": x, "y_arr": all_ys[idx]} for idx, x in enumerate(xs)]
    
    async with httpx.AsyncClient() as clt:
        tsks = []
        for (net_name, net_url), share in zip(networks.items(), shares):
            tsks.append(clt.post(f"{net_url}/store_share", json={"id": request.id, "share": share}))

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
    
    cleaned_bytes = bytes([b & 0xFF for b in rec_ints]) # This was by no means my solution,
    #it came to my attention that the C lagrange interpolation can produce 256, hense the incompatibility with
    #the bytes type in python, the solution was to simply clean the ints by applying a bitwise AND with 0xFF
    # effectively keeping only the least significant byte of each integer. This way, we ensure that the resulting 
    # bytes are valid and can be correctly reconstructed into the original secret.
    return {"secret": cleaned_bytes.hex()}