from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from models.abonos_model import AbonoItem, AbonoOut

TIPO_PAGO_INICIAL = "pago_inicial"
TIPO_ABONO = "abono"

EFECTIVO = "Efectivo"
# "Crédito" no se cobra en caja: es el saldo que queda en cuentas por cobrar
FORMAS_PAGO = [
    EFECTIVO, "Nota de Crédito", "Vale", "Cheque", "Tarjeta de Crédito", "Cortesía",
    "Depósito Bancario", "Vale de Descuento", "Bancomer", "Banamex", "Santander", "AMEX", "CLIP",
]


class Pagos(Base):
    """Cobro hecho en caja; puede cubrir varias cotizaciones y combinar formas de pago."""
    __tablename__ = "pagos"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(20), nullable=False, default=TIPO_PAGO_INICIAL)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    recibido = Column(Numeric(10, 2), nullable=False)
    cambio = Column(Numeric(10, 2), nullable=False, default=0)
    observaciones = Column(String(500), nullable=True)

    formas = relationship("PagoForma", cascade="all, delete-orphan", order_by="PagoForma.id")


class PagoForma(Base):
    __tablename__ = "pago_formas"

    id = Column(Integer, primary_key=True, index=True)
    pago_id = Column(Integer, ForeignKey("pagos.id", ondelete="CASCADE"), nullable=False, index=True)
    forma = Column(String(40), nullable=False)
    referencia = Column(String(100), nullable=True)
    importe = Column(Numeric(10, 2), nullable=False)


class PagoFormaIn(BaseModel):
    forma: str
    referencia: str | None = Field(None, max_length=100)
    importe: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class PagoInicialCreate(BaseModel):
    sucursal_id: int
    cotizacion_ids: list[int] = Field(min_length=1)
    formas: list[PagoFormaIn] = Field(min_length=1)
    observaciones: str | None = Field(None, max_length=500)


class AbonosCobro(BaseModel):
    """Abonos a saldos (pagos parciales o cuentas por cobrar) cobrados en caja con sus formas de pago."""
    sucursal_id: int
    abonos: list[AbonoItem] = Field(min_length=1)
    formas: list[PagoFormaIn] = Field(min_length=1)
    observaciones: str | None = Field(None, max_length=500)


class PagoFormaOut(BaseModel):
    forma: str
    referencia: str | None
    importe: Decimal

    class Config:
        from_attributes = True


class PagoOut(BaseModel):
    id: int
    tipo: str
    cliente_id: int
    sucursal_id: int
    fecha: datetime
    total: Decimal
    recibido: Decimal
    cambio: Decimal
    observaciones: str | None
    formas: list[PagoFormaOut]
    cotizacion_ids: list[int]


class PagoInicialProductoOut(BaseModel):
    nombre: str
    cantidad: int
    subtotal: Decimal


class PagoInicialPendienteOut(BaseModel):
    """Presupuesto cuyo pago inicial aun no se cobra."""
    id: int
    tipo_venta: str
    plazo: str
    fecha: datetime
    vencimiento: datetime | None
    total_venta: Decimal
    pago_inicial: Decimal
    detalles: list[PagoInicialProductoOut]


class PagoParcialOut(BaseModel):
    """Venta (de cualquier tipo) con saldo pendiente despues del pago inicial."""
    id: int
    tipo_venta: str
    plazo: str
    fecha: datetime
    total_venta: Decimal
    pago_inicial: Decimal
    total_pagado: Decimal
    diferencia: Decimal
    detalles: list[PagoInicialProductoOut]
    abonos: list[AbonoOut]


class LiquidacionOut(BaseModel):
    """Venta pagada por completo."""
    id: int
    sucursal: str
    ticket: int | None
    folio: str | None
    importe_total: Decimal
    impresa: bool
    fecha_liquidacion: datetime


class LiquidacionesPaginaOut(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[LiquidacionOut]


class LiquidacionPagoOut(BaseModel):
    concepto: str
    fecha: datetime
    monto: Decimal
    cobro_id: int | None
    cobro_total: Decimal | None
    formas: list[PagoFormaOut]


class LiquidacionDetalleOut(BaseModel):
    id: int
    sucursal: str
    tipo_venta: str
    plazo: str
    fecha_venta: datetime
    fecha_liquidacion: datetime
    total_venta: Decimal
    impresa: bool
    detalles: list[PagoInicialProductoOut]
    pagos: list[LiquidacionPagoOut]
