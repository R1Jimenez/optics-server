from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class AtributosValores(Base):
    __tablename__ = "atributosvalores"

    id = Column(Integer, primary_key=True, index=True)
    atributo_id = Column(Integer, nullable=False)
    clave = Column(String(20), nullable=False)
    descripcion = Column(String(100), nullable=False)

class AtribValoresCreate(BaseModel):
    atributo_id: int
    descripcion: str

class AtribValoresUpdate(BaseModel):
    atributo_id: int | None = None
    clave: str | None = None
    descripcion: str | None = None

class AtribValoresOutput(BaseModel):
    id:int
    atributo_id: int
    clave: str
    descripcion: str

    class Config:
        from_attributes = True