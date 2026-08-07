from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey, Table
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, field_serializer
from typing import Optional, Any

# Tabla intermedia para la relación many-to-many entre Order y Productos
order_productos = Table(
    'order_productos',
    Base.metadata,
    Column('order_id', Integer, ForeignKey('orders.id'), primary_key=True),
    Column('producto_id', Integer, ForeignKey('productos.id'), primary_key=True),
    Column('cantidad', Integer, default=1, nullable=False)
)

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    tipo_venta_id = Column(Integer, ForeignKey('tipo_venta.id'), nullable=False)
    plazo_id = Column(Integer, ForeignKey('plazo.id'), nullable=False)
    pago_inicial = Column(Numeric(10, 2), nullable=False)
    
    # Relaciones
    tipo_venta = relationship("TipoVenta", foreign_keys=[tipo_venta_id])
    plazo = relationship("Plazo", foreign_keys=[plazo_id])
    productos = relationship("Productos", secondary=order_productos, backref="orders")

# Schema para item de producto en la orden (incluye cantidad)
class OrderProductoItem(BaseModel):
    producto_id: int
    cantidad: int = 1

class OrderCreate(BaseModel):
    tipo_venta_id: int
    plazo_id: int
    pago_inicial: float
    productos: list[OrderProductoItem]

class OrderUpdate(BaseModel):
    tipo_venta_id: Optional[int] = None
    plazo_id: Optional[int] = None
    pago_inicial: Optional[float] = None
    productos: Optional[list[OrderProductoItem]] = None

# Schema para producto en la respuesta
class ProductoEnOrden(BaseModel):
    id: int
    categoria: str
    codigo: str
    producto: str
    precio: float
    existencia: int
    
    class Config:
        from_attributes = True

class OrderOut(BaseModel):
    id: int
    tipo_venta: Any
    plazo: Any
    pago_inicial: float
    productos: list[ProductoEnOrden]

    class Config:
        from_attributes = True
    
    @field_serializer('tipo_venta')
    def serialize_tipo_venta(self, tipo_venta: Any) -> str:
        if hasattr(tipo_venta, 'venta'):
            return tipo_venta.venta
        return str(tipo_venta)
    
    @field_serializer('plazo')
    def serialize_plazo(self, plazo: Any) -> str:
        if hasattr(plazo, 'plazo'):
            return plazo.plazo
        return str(plazo)