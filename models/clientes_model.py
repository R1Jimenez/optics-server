from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, EmailStr
from datetime import datetime

class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    rfc = Column(String(16), nullable=False)
    calle = Column(String(200), nullable=False)
    numero = Column(String(50), nullable=False)
    colonia = Column(String(100), nullable=False)
    ciudad = Column(String(100), nullable=False)
    estado = Column(String(100), nullable=False)
    codigopostal = Column(String(20), nullable=False)
    telefono = Column(String(30), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    contacto = Column(String(100), nullable=False)
    tipocliente = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    

class CreateCliente(BaseModel):
    nombres: str
    apellidos: str
    rfc: str | None = None
    calle: str
    numero: str
    colonia: str
    ciudad: str
    estado: str
    codigopostal: str
    telefono: str
    email: EmailStr
    contacto: str
    tipocliente: int


class ClienteUpdate(BaseModel):
    nombres: str | None = None
    apellidos: str | None = None
    rfc: str | None = None
    calle: str | None = None
    numero: str | None = None
    colonia: str | None = None
    ciudad: str | None = None
    estado: str | None = None
    codigopostal: str | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    contacto: str | None = None
    tipocliente: int | None = None

class ClienteOut(BaseModel):
    id: int
    nombres: str
    apellidos: str
    rfc: str
    calle: str
    numero: str
    colonia: str
    ciudad: str
    estado: str
    codigopostal: str
    telefono: str
    email: EmailStr
    contacto: str
    tipocliente: int | None = None

    class Config:
        from_attributes = True