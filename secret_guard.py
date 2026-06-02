from fastapi import FastAPI, HTTPException, Depends
import httpx
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from os import getenv

DATABASE_URL = getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
app = FastAPI()

def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()

class Share(Base):
    __tablename__ = "shares"
    id = Column(String, primary_key=True, index=True)
    x = Column(Integer)
    y_arr = Column(JSON)

class ShareCoords(BaseModel):
    x: int
    y_arr: list[int]

class ShareCreate(BaseModel):
    id: str
    share: ShareCoords

Base.metadata.create_all(bind=engine)



@app.post("/store_share")
def store_share(share: ShareCreate, db=Depends(get_db)):
    existing_share = db.query(Share).filter(Share.id == share.id).first()
    if existing_share:
        raise HTTPException(status_code=400, detail="Share with this ID already exists")

    new_share = Share(id=share.id, x=share.share.x, y_arr=share.share.y_arr)
    db.add(new_share)
    db.commit()
    db.refresh(new_share)
    return {"message": "Share stored successfully"}

@app.get("/get_share")
def get_share(id: str, db=Depends(get_db)):
    share = db.query(Share).filter(Share.id == id).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"id": share.id, "share": {"x": share.x, "y_arr": share.y_arr}}
