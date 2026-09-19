from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel
from datetime import datetime
from models.info_referencial_model import InfoReferencialOut


class OrdenesTrabajo(Base):
    __tablename__ = "ordenes_trabajo"
    __table_args__ = (
        UniqueConstraint("id_cotizacion", name="uq_ordenes_trabajo_id_cotizacion"),
    )

    id = Column(Integer, primary_key=True, index=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    id_cliente = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    id_paciente = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    id_cotizacion = Column(Integer, ForeignKey("Cotizaciones.id"), nullable=True)

    sucursal = relationship("Sucursal", backref="ordenes_trabajo")
    usuario = relationship("User", backref="ordenes_trabajo")
    cliente = relationship("Cliente", backref="ordenes_trabajo")
    paciente = relationship("Paciente", backref="ordenes_trabajo")
    cotizacion = relationship("Cotizaciones", backref="orden_trabajo")


class OrdenTrabajoCreate(BaseModel):
    sucursal_id: int
    usuario_id: int
    id_cliente: int
    id_paciente: int | None = None
    id_cotizacion: int | None = None


class OrdenTrabajoUpdate(BaseModel):
    sucursal_id: int | None = None
    usuario_id: int | None = None
    id_cliente: int | None = None
    id_paciente: int | None = None
    id_cotizacion: int | None = None


# Sub-esquemas usados unicamente para armar la vista de la orden de trabajo
class OrdenTrabajoSucursalOut(BaseModel):
    id: int
    sucursal: str

    class Config:
        from_attributes = True


class OrdenTrabajoClienteOut(BaseModel):
    id: int
    nombres: str
    apellidos: str

    class Config:
        from_attributes = True


class OrdenTrabajoUsuarioOut(BaseModel):
    id: int
    nombres: str
    apellidos: str

    class Config:
        from_attributes = True


class OrdenTrabajoPacienteOut(BaseModel):
    id: int
    nombres: str
    apellidos: str

    class Config:
        from_attributes = True


class OrdenTrabajoProductoOut(BaseModel):
    nombre: str
    codigo_externo: str
    cantidad: int

    class Config:
        from_attributes = True


class OrdenTrabajoOut(BaseModel):
    id: int
    sucursal: OrdenTrabajoSucursalOut
    cliente: OrdenTrabajoClienteOut
    usuario: OrdenTrabajoUsuarioOut
    paciente: OrdenTrabajoPacienteOut | None = None
    info_referencial: InfoReferencialOut | None = None
    promesa_entrega: datetime | None = None
    fecha: datetime
    detalles: list[OrdenTrabajoProductoOut]

    class Config:
        from_attributes = True

