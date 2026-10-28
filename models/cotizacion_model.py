from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
from models.clientes_model import ClienteOut


class Cotizaciones(Base):
    __tablename__ = "Cotizaciones"

    id = Column(Integer, primary_key=True, index=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    id_cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    id_paciente = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    tipo_venta = Column(Integer, ForeignKey("tipo_venta.id"), nullable=False)
    plazo = Column(Integer, ForeignKey("plazo.id"), nullable=False)
    pago_inicial = Column(Numeric(10, 2), nullable=False)
    pago_restante = Column(Numeric(10, 2), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)
    promesa_entrega = Column(DateTime, nullable=True)
    vencimiento = Column(DateTime, nullable=True)
    total_normal = Column(Numeric(10, 2), nullable=False)
    total_venta = Column(Numeric(10, 2), nullable=False)
    active = Column(Boolean, default=True)
    promocion_id = Column(Integer, ForeignKey("promociones.id"), nullable=True)

    sucursal = relationship("Sucursal", backref="cotizaciones")
    usuario = relationship("User", backref="cotizaciones")
    cliente = relationship("Cliente", backref="cotizaciones")
    paciente = relationship("Paciente", backref="cotizaciones")
    tipo_venta_rel = relationship("TipoVenta", backref="cotizaciones")
    plazo_rel = relationship("Plazo", backref="cotizaciones")
    detalles = relationship("CotizacionDetalle", backref="cotizacion", cascade="all, delete-orphan")


class CotizacionDetalle(Base):
    """Un renglon por cada producto agregado a la cotizacion; permite repetir el mismo producto en varios renglones."""
    __tablename__ = "CotizacionDetalle"

    id = Column(Integer, primary_key=True, index=True)
    cotizacion_id = Column(Integer, ForeignKey("Cotizaciones.id", ondelete="CASCADE"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    # descuento total aplicado al renglon (tipo de cliente y/o promocion); null en ventas anteriores a promociones
    descuento_porcentaje = Column(Numeric(5, 2), nullable=True)

    producto = relationship("Productos")


class CotizacionDetalleCreate(BaseModel):
    producto_id: int
    cantidad: int = 1


class CotizacionDetalleOut(BaseModel):
    id: int
    producto_id: int
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    descuento_porcentaje: Decimal | None = None

    class Config:
        from_attributes = True


class CotizacionCreate(BaseModel):
    sucursal_id: int
    usuario_id: int
    id_cliente: int
    id_paciente: int
    tipo_venta: int
    plazo: int
    pago_inicial: Decimal
    promesa_entrega: datetime | None = None
    productos: list[CotizacionDetalleCreate]
    promocion_id: int | None = None


class CotizacionUpdate(BaseModel):
    sucursal_id: int | None = None
    usuario_id: int | None = None
    id_cliente: int | None = None
    id_paciente: int | None = None
    tipo_venta: int | None = None
    plazo: int | None = None
    pago_inicial: Decimal | None = None
    promesa_entrega: datetime | None = None
    productos: list[CotizacionDetalleCreate] | None = None


class CotizacionOut(BaseModel):
    id: int
    sucursal_id: int
    usuario_id: int
    id_cliente: int
    id_paciente: int
    tipo_venta: int
    plazo: int
    pago_inicial: Decimal
    pago_restante: Decimal
    fecha: datetime
    promesa_entrega: datetime | None = None
    vencimiento: datetime | None = None
    total_normal: Decimal
    total_venta: Decimal
    active: bool
    promocion_id: int | None = None
    detalles: list[CotizacionDetalleOut]

    class Config:
        from_attributes = True


class CotizacionEnEsperaOut(BaseModel):
    id: int
    fecha: datetime
    cliente: ClienteOut

    class Config:
        from_attributes = True


class TicketResumenOut(BaseModel):
    id: int
    fecha: datetime
    cliente: str
    importe: Decimal


class TicketsPaginaOut(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[TicketResumenOut]


class TicketItemOut(BaseModel):
    cantidad: int
    nombre: str
    precio_unitario: Decimal
    descuento_porcentaje: Decimal


class TicketOut(BaseModel):
    """Datos necesarios para reimprimir el ticket de una venta tal como se emitio."""
    folio: int
    fecha: datetime
    sucursal: str
    vendedor: str
    cliente_nombre: str
    cliente_direccion: str
    cliente_telefono: str
    tipo_cliente: str | None = None
    paciente: str | None = None
    plazo: str | None = None
    promocion: str | None = None
    items: list[TicketItemOut]
    total_normal: Decimal
    total_venta: Decimal
    descuento_porcentaje: Decimal
    pago_inicial: Decimal
    pago_restante: Decimal
    promesa_entrega: datetime | None = None