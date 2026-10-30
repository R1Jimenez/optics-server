from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from database.database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

TIPO_ENTRADA = "Entrada"
TIPO_SALIDA = "Salida"

TipoConexion = Literal["Entrada", "Salida"]


class HistorialConexion(Base):
    __tablename__ = "historial_conexiones"

    id = Column(Integer, primary_key=True, index=True)
    # usuario y nombre se copian para conservar el historial aunque el usuario cambie o se elimine
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    usuario = Column(String(50), nullable=False)
    nombre = Column(String(201), nullable=False)
    tipo = Column(String(10), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ConexionOut(BaseModel):
    id: int
    user_id: int | None
    usuario: str
    nombre: str
    tipo: str
    fecha: datetime

    class Config:
        from_attributes = True


class ConexionesPaginaOut(BaseModel):
    total: int
    pagina: int
    por_pagina: int
    items: list[ConexionOut]
