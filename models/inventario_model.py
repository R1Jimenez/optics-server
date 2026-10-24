from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from database.database import Base
from pydantic import BaseModel
from datetime import datetime

TIPO_INVENTARIO_INICIAL = "Inventario Inicial"
TIPO_ENTRADA_AJUSTE = "Entrada por Ajuste"
TIPO_SALIDA_AJUSTE = "Salida por Ajuste"
TIPO_AJUSTE = "Ajuste de Inventario"
TIPO_SALIDA_VENTA = "Salida por Venta"
TIPO_ENTRADA_MODIFICACION_VENTA = "Entrada por Modificacion de Venta"
TIPO_ENTRADA_CANCELACION_VENTA = "Entrada por Cancelacion de Venta"
TIPO_SALIDA_TRASPASO = "Salida por Traspaso"
TIPO_ENTRADA_TRASPASO = "Entrada por Traspaso"
TIPO_ENTRADA_CANCELACION_TRASPASO = "Entrada por Cancelacion de Traspaso"

TIPOS_MOVIMIENTO = [
    TIPO_INVENTARIO_INICIAL,
    TIPO_ENTRADA_AJUSTE,
    TIPO_SALIDA_AJUSTE,
    TIPO_AJUSTE,
    TIPO_SALIDA_VENTA,
    TIPO_ENTRADA_MODIFICACION_VENTA,
    TIPO_ENTRADA_CANCELACION_VENTA,
    TIPO_SALIDA_TRASPASO,
    TIPO_ENTRADA_TRASPASO,
    TIPO_ENTRADA_CANCELACION_TRASPASO,
]

# Tipos que el usuario puede indicar al registrar un movimiento manual
TIPOS_MOVIMIENTO_MANUAL = [TIPO_INVENTARIO_INICIAL, TIPO_ENTRADA_AJUSTE, TIPO_SALIDA_AJUSTE, TIPO_AJUSTE]

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
    tipo = Column(String(60), nullable=True)
    referencia = Column(String(100), nullable=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)

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
    tipo: str | None = None
    referencia: str | None = None

class InventarioMovimientoOut(BaseModel):
    id: int
    inventario_id: int
    entrada: int
    merma: int
    existencia_final: int
    fecha: datetime
    tipo: str | None = None
    referencia: str | None = None
    usuario_id: int | None = None

    class Config:
        from_attributes = True

class MovimientoDetalleOut(BaseModel):
    id: int
    fecha: datetime
    sucursal_id: int
    sucursal: str
    producto_id: int
    codigo: str
    producto: str
    tipo: str
    referencia: str | None = None
    usuario: str | None = None
    existencia_anterior: int
    entradas: int
    salidas: int
    saldo: int

class MovimientosPaginaOut(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[MovimientoDetalleOut]

class ProductoInventarioOut(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    descripcion: str
    existencia_actual: int
    punto_reorden: int

    class Config:
        from_attributes = True

class ProductoBusquedaOut(ProductoInventarioOut):
    codigo_externo: str
