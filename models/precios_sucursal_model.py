from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class PreciosSucursal(Base):
    __tablename__= "preciosucursal"

    id = Column(Integer, primary_key=True, index=True)
    sucursal = Column(Integer, nullable=False)
    producto = Column(Integer, nullable=False)
    costo = Column(Numeric, nullable=True)
    precio = Column(Numeric, nullable=False)

    __table_args__ = (
        UniqueConstraint('sucursal', 'producto', name='uq_sucursal_producto'),
    )

class PrecioSucursalCreate(BaseModel):
    sucursal: int
    producto: int
    costo: float
    precio: float

class PrecioSucursalUpdate(BaseModel):
    sucursal: int | None = None
    producto: int | None = None
    costo: float | None = None
    precio: float | None = None

class PrecioSucursalOut(BaseModel):
    id: int
    sucursal: int
    producto: int
    costo: float | None
    precio: float

    class config:
        from_attributes = True