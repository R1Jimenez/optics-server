from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Productos(Base):
    __tablename__ = "productos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(500), nullable=False)
    codigo = Column(String(100), nullable=False)
    codigo_externo = Column(String(50), nullable=False)
    descripcion = Column(String(255), nullable=False)
    estatus = Column(Integer, nullable=False)
    tipo = Column(Integer, nullable=False)
    genera_orden = Column(Integer, nullable=False)
    unidad = Column(String(50), nullable=False)
    tipo_iva = Column(Integer, nullable=False)  

class ProductoCreate(BaseModel):
    atributos_seleccionados: dict[int, int | None]
    codigo_externo: str
    descripcion: str
    estatus: int = 1
    tipo: int
    genera_orden: int = 0
    unidad: str
    tipo_iva: int

class ProductoAtributo(Base):
    __tablename__ = "producto_atributos"

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, nullable=False)
    atributo_id = Column(Integer, nullable=False)
    atributovalor_id = Column(Integer, nullable=False)

class ProductOut(BaseModel):
    id: int
    nombre: str
    codigo: str
    codigo_externo: str
    descripcion: str
    estatus: int
    tipo: int
    genera_orden: int
    unidad: str
    tipo_iva: int
    atributos_seleccionados: dict[int, int]

    class Config:
        from_attributes = True