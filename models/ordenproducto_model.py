from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime


class OrdenProducto(Base):
    __tablename__ = "OrdenProducto"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    id_tipo_prod = Column(Integer, ForeignKey("TipProd.id"), nullable=False)
    id_marca_prod = Column(Integer, ForeignKey("MarcaProd.id"), nullable=False)
    id_modelo_prod = Column(Integer, ForeignKey("ModeloProd.id"), nullable=False)
    id_tipo_lente = Column(Integer, ForeignKey("TipoLente.id"), nullable=True)
    id_materia_lente = Column(Integer, ForeignKey("MateriaLente.id"), nullable=True)
    id_color_lente = Column(Integer, ForeignKey("ColorLente.id"), nullable=True)
    id_rango_lente = Column(Integer, ForeignKey("RangoLente.id"), nullable=True)

    # Relationships
    tipo_prod = relationship("TipProd", backref="productos")
    marca_prod = relationship("MarcaProd", backref="productos")
    modelo_prod = relationship("ModeloProd", backref="productos")
    tipo_lente = relationship("TipoLente", backref="productos")
    materia_lente = relationship("MateriaLente", backref="productos")
    color_lente = relationship("ColorLente", backref="productos")
    rango_lente = relationship("RangoLente", backref="productos")


class OrdenProductoCreate(BaseModel):
    id_tipo_prod: int
    id_marca_prod: int
    id_modelo_prod: int
    id_tipo_lente: int | None = None
    id_materia_lente: int | None = None
    id_color_lente: int | None = None
    id_rango_lente: int | None = None


class OrdenProductoUpdate(BaseModel):
    id_tipo_prod: int | None = None
    id_marca_prod: int | None = None
    id_modelo_prod: int | None = None
    id_tipo_lente: int | None = None
    id_materia_lente: int | None = None
    id_color_lente: int | None = None
    id_rango_lente: int | None = None


class OrdenProductoOut(BaseModel):
    id: int
    id_tipo_prod: int
    id_marca_prod: int
    id_modelo_prod: int
    id_tipo_lente: int | None = None
    id_materia_lente: int | None = None
    id_color_lente: int | None = None
    id_rango_lente: int | None = None

    class Config:
        from_attributes = True