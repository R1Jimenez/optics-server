from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Armazon(Base):
    __tablename__ = "armazones"

    id = Column(Integer, primary_key=True, index=True)
    marca = Column(String(100), nullable=False)
    precio = Column(Numeric(10, 2), nullable=False)

class ArmazonCreate(BaseModel):
    marca: str
    precio: float

class ArmazonUpdate(BaseModel):
    marca: str | None = None
    precio: float | None = None

class ArmazonOut(BaseModel):
    id: int
    marca: str
    precio: float

    class Config:
        from_attributes = True