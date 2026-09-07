from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, EmailStr
from datetime import datetime

class Tipo_Cliente(Base):

    __tablename__ = "tipo_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(String(100), nullable=False)
    porcentaje_descuento = Column(Integer, nullable=False)

class TipoClienteCreate(BaseModel):
    cliente: str
    porcentaje_descuento: int

class TipoClienteUpdate(BaseModel):
    cliente: str | None = None
    porcentaje_descuento: int | None = None

class TipoClienteOut(BaseModel):
    id: int
    cliente: str
    porcentaje_descuento: int

    class Config:
        from_attributes = True