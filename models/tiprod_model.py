from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class TipProd(Base):
    __tablename__ = "TipProd"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(50), nullable=False)

class TipProdCreate(BaseModel):
    descripcion: str

class TiProdUpdate(BaseModel):
    descripcion: str | None = None

class TiProdOut(BaseModel):
    id: int
    descripcion: str

    class Config:
        from_attributes = True