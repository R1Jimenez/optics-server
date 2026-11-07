from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class TipoVenta(Base):
    __tablename__ = "tipo_venta"

    id = Column(Integer, primary_key=True, index=True)
    venta = Column(String(50), nullable=False)
    # credito: el saldo tambien aparece en Cuentas por Cobrar
    es_credito = Column(Boolean, nullable=False, default=False, server_default="false")

class TipoVentaCreate(BaseModel):
    venta: str
    es_credito: bool = False

class TipoVentaUpdate(BaseModel):
    venta: str | None = None
    es_credito: bool | None = None

class TipoVentaOut(BaseModel):
    id: int
    venta: str
    es_credito: bool = False

    class Config:
        from_attributes = True