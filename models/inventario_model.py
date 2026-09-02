from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from database.database import Base
from pydantic import BaseModel
from datetime import datetime

class InventarioSucursal(Base):
    __tablename__ = "inventario_sucursal"

    id = Column(Integer, primary_key=True, index=True)
    sucursal_id = Column(Integer, nullable=False)
    producto_id = Column(Integer, nullable=False)
    existencia_actual = Column(Integer, nullable=False, default=0)
    punto_reorden = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint('sucursal_id', 'producto_id', name='uq_sucursal_producto_inventario'),
    )

class InventarioMovimiento(Base):
    __tablename__ = "inventario_movimiento"

    id = Column(Integer, primary_key=True, index=True)
    inventario_id = Column(Integer, ForeignKey("inventario_sucursal.id"), nullable=False)
    entrada = Column(Integer, nullable=False, default=0)
    merma = Column(Integer, nullable=False, default=0)
    existencia_final = Column(Integer, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)

class InventarioSucursalCreate(BaseModel):
    sucursal_id: int
    producto_id: int
    punto_reorden: int = 0

class InventarioSucursalUpdate(BaseModel):
    punto_reorden: int | None = None

class InventarioSucursalOut(BaseModel):
    id: int
    sucursal_id: int
    producto_id: int
    existencia_actual: int
    punto_reorden: int

    class Config:
        from_attributes = True

class InventarioMovimientoCreate(BaseModel):
    sucursal_id: int
    producto_id: int
    entrada: int = 0
    merma: int = 0

class InventarioMovimientoOut(BaseModel):
    id: int
    inventario_id: int
    entrada: int
    merma: int
    existencia_final: int
    fecha: datetime

    class Config:
        from_attributes = True
