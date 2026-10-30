from sqlalchemy import Column, Integer, String
from database.database import Base
from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated

NombreTipo = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Porcentaje = Annotated[int, Field(ge=0, le=100)]

class Tipo_Cliente(Base):

    __tablename__ = "tipo_cliente"

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(String(100), nullable=False)
    porcentaje_descuento = Column(Integer, nullable=False)

class TipoClienteCreate(BaseModel):
    cliente: NombreTipo
    porcentaje_descuento: Porcentaje

class TipoClienteUpdate(BaseModel):
    cliente: NombreTipo | None = None
    porcentaje_descuento: Porcentaje | None = None

class TipoClienteOut(BaseModel):
    id: int
    cliente: str
    porcentaje_descuento: int
    # solo lo llena /all: clientes asignados a este tipo
    clientes: int | None = None

    class Config:
        from_attributes = True