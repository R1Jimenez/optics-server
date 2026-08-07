from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Servicio(Base):
    __tablename__ = "servicios"

    id = Column(Integer, primary_key=True, index=True)
    servicio = Column(String(100), nullable=False)
    precio = Column(Numeric(10, 2), nullable=False)

class ServicioCreate(BaseModel):
    servicio: str
    precio: float

class ServicioUpdate(BaseModel):
    servicio: str | None = None
    precio: float | None = None

class ServicioOut(BaseModel):
    id: int
    servicio: str
    precio: float
    
    class Config:
        from_attributes = True