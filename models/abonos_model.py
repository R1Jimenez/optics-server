from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from database.database import Base
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

TIPO_PAGO = "pago"
TIPO_INCOBRABLE = "incobrable"


class Abonos(Base):
    """Movimiento que reduce el saldo (pago_restante) de una cotizacion: un pago del cliente o un castigo por incobrable."""
    __tablename__ = "abonos"

    id = Column(Integer, primary_key=True, index=True)
    cotizacion_id = Column(Integer, ForeignKey("Cotizaciones.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    tipo = Column(String(20), nullable=False, default=TIPO_PAGO)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)


class AbonoItem(BaseModel):
    cotizacion_id: int
    monto: Decimal = Field(gt=0)


class AbonosAplicar(BaseModel):
    abonos: list[AbonoItem] = Field(min_length=1)


class AbonoOut(BaseModel):
    id: int
    cotizacion_id: int
    usuario_id: int
    monto: Decimal
    tipo: str
    fecha: datetime

    class Config:
        from_attributes = True


class CuentaPorCobrarProductoOut(BaseModel):
    producto_id: int
    nombre: str
    cantidad: int
    subtotal: Decimal


class CuentaPorCobrarOut(BaseModel):
    id: int
    concepto: str
    emision: datetime
    vencimiento: datetime | None = None
    importe: Decimal
    total_pagado: Decimal
    diferencia: Decimal
    detalles: list[CuentaPorCobrarProductoOut]
    abonos: list[AbonoOut]
