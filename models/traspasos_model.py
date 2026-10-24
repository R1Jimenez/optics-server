from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, Field
from datetime import datetime

ESTATUS_NUEVO = "Nuevo"
ESTATUS_ENVIADO = "Enviado"
ESTATUS_RECIBIDO = "Recibido"
ESTATUS_CANCELADO = "Cancelado"

ESTATUS_TRASPASO = [ESTATUS_NUEVO, ESTATUS_ENVIADO, ESTATUS_RECIBIDO, ESTATUS_CANCELADO]


class Traspasos(Base):
    __tablename__ = "traspasos"

    id = Column(Integer, primary_key=True, index=True)
    comentarios = Column(String(500), nullable=True)
    sucursal_origen_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False, index=True)
    sucursal_destino_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False, index=True)
    estatus = Column(String(20), nullable=False, default=ESTATUS_NUEVO, index=True)
    promesa_entrega = Column(DateTime, nullable=True)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    modificado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_modificacion = Column(DateTime, default=datetime.utcnow, nullable=False)

    origen = relationship("Sucursal", foreign_keys=[sucursal_origen_id])
    destino = relationship("Sucursal", foreign_keys=[sucursal_destino_id])
    creador = relationship("User", foreign_keys=[creado_por])
    modificador = relationship("User", foreign_keys=[modificado_por])
    detalles = relationship(
        "TraspasoDetalle", backref="traspaso", cascade="all, delete-orphan", order_by="TraspasoDetalle.id"
    )


class TraspasoDetalle(Base):
    __tablename__ = "traspaso_detalle"

    id = Column(Integer, primary_key=True, index=True)
    traspaso_id = Column(Integer, ForeignKey("traspasos.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad_solicitada = Column(Integer, nullable=False)
    cantidad_enviada = Column(Integer, nullable=True)
    cantidad_recibida = Column(Integer, nullable=True)

    producto = relationship("Productos")


class TraspasoItem(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0)


class TraspasoCreate(BaseModel):
    comentarios: str | None = Field(None, max_length=500)
    sucursal_origen_id: int
    sucursal_destino_id: int
    promesa_entrega: datetime | None = None
    productos: list[TraspasoItem] = Field(min_length=1)


class TraspasoResumenOut(BaseModel):
    id: int
    origen: str
    destino: str
    estatus: str
    promesa_entrega: datetime | None = None
    creado_por: str
    fecha_creacion: datetime
    modificado_por: str
    fecha_modificacion: datetime


class TraspasosPaginaOut(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[TraspasoResumenOut]


class TraspasoDetalleOut(BaseModel):
    producto_id: int
    codigo: str
    nombre: str
    descripcion: str
    codigo_externo: str
    punto_reorden: int
    existencia_origen: int
    cantidad_solicitada: int
    cantidad_enviada: int | None = None
    cantidad_recibida: int | None = None


class TraspasoOut(TraspasoResumenOut):
    comentarios: str | None = None
    sucursal_origen_id: int
    sucursal_destino_id: int
    detalles: list[TraspasoDetalleOut]
