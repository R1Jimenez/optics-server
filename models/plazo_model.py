from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Plazo(Base):
    __tablename__ = "plazo"

    id = Column(Integer, primary_key=True, index=True)
    plazo = Column(String(100), nullable=False)
    tipo_venta_id = Column(Integer, nullable=False) 

class PlazoCreate(BaseModel):
    plazo: str
    tipo_venta_id: int

class PlazoUpdate(BaseModel):
    plazo: str | None = None
    tipo_venta_id: int | None = None

class PlazoOut(BaseModel):
    id: int
    plazo: str
    tipo_venta_id: int

    class Config:
        from_attributes = True