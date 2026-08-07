from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class TipoVenta(Base):
    __tablename__ = "tipo_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta = Column(String(50), nullable=False)

class TipoVentaCreate(BaseModel):
    venta: str

class TipoVentaUpdate(BaseModel):
    venta: str | None = None

class TipoVentaOut(BaseModel):
    id: int
    venta: str

    class Config:
        from_attributes = True