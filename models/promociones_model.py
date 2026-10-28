from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, Field


class Promociones(Base):
    __tablename__ = "promociones"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    descuento = Column(Numeric(5, 2), nullable=False)
    descuento_max_vendedor = Column(Numeric(5, 2), nullable=False, default=0)
    acumulativa = Column(Boolean, nullable=False, default=False)
    permanente = Column(Boolean, nullable=False, default=False)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    creado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    modificado_por = Column(Integer, ForeignKey("users.id"), nullable=False)
    fecha_modificacion = Column(DateTime, default=datetime.utcnow, nullable=False)

    creador = relationship("User", foreign_keys=[creado_por])
    modificador = relationship("User", foreign_keys=[modificado_por])
    sucursales = relationship("PromocionSucursal", cascade="all, delete-orphan", order_by="PromocionSucursal.id")
    condiciones = relationship("PromocionCondicion", cascade="all, delete-orphan", order_by="PromocionCondicion.id")


class PromocionSucursal(Base):
    """Sucursales donde aplica la promocion."""
    __tablename__ = "promocion_sucursal"
    __table_args__ = (
        UniqueConstraint("promocion_id", "sucursal_id", name="uq_promocion_sucursal"),
    )

    id = Column(Integer, primary_key=True, index=True)
    promocion_id = Column(Integer, ForeignKey("promociones.id", ondelete="CASCADE"), nullable=False, index=True)
    sucursal_id = Column(Integer, ForeignKey("sucursales.id"), nullable=False)

    sucursal = relationship("Sucursal")


# Categorias de condicion. Dentro de cada grupo solo puede usarse una; una lista vacia significa "aplica a todos".
CATEGORIAS_CONDICION = ("tipos_venta", "plazos", "productos", "atributos_valores", "clientes", "tipos_cliente")
GRUPOS_CONDICION = (("tipos_venta", "plazos"), ("productos", "atributos_valores"), ("clientes", "tipos_cliente"))


class PromocionCondicion(Base):
    """Restriccion de a que tipos de venta, plazos, productos, atributos, clientes o tipos de cliente aplica la promocion."""
    __tablename__ = "promocion_condicion"
    __table_args__ = (
        UniqueConstraint("promocion_id", "categoria", "referencia_id", name="uq_promocion_condicion"),
    )

    id = Column(Integer, primary_key=True, index=True)
    promocion_id = Column(Integer, ForeignKey("promociones.id", ondelete="CASCADE"), nullable=False, index=True)
    # uno de CATEGORIAS_CONDICION; referencia_id apunta a la tabla de esa categoria
    categoria = Column(String(30), nullable=False)
    referencia_id = Column(Integer, nullable=False)


class PromocionCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    descuento: Decimal = Field(gt=0, le=100)
    descuento_max_vendedor: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    acumulativa: bool = False
    permanente: bool = False
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    sucursales: list[int] = Field(min_length=1)
    tipos_venta: list[int] = []
    plazos: list[int] = []
    productos: list[int] = []
    atributos_valores: list[int] = []
    clientes: list[int] = []
    tipos_cliente: list[int] = []


class PromocionSucursalOut(BaseModel):
    id: int
    sucursal: str


class PromocionReferenciaOut(BaseModel):
    id: int
    etiqueta: str


class PromocionOut(BaseModel):
    id: int
    nombre: str
    descuento: Decimal
    descuento_max_vendedor: Decimal
    acumulativa: bool
    permanente: bool
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    activo: bool
    vigente: bool
    sucursales: list[PromocionSucursalOut]
    tipos_venta: list[PromocionReferenciaOut] = []
    plazos: list[PromocionReferenciaOut] = []
    productos: list[PromocionReferenciaOut] = []
    atributos_valores: list[PromocionReferenciaOut] = []
    clientes: list[PromocionReferenciaOut] = []
    tipos_cliente: list[PromocionReferenciaOut] = []
    creado_por: str
    fecha_creacion: datetime
    modificado_por: str
    fecha_modificacion: datetime
