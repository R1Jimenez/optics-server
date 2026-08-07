from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class MateriaLente(Base):
    __tablename__ = "MateriaLente"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(50), nullable=False)

class MateriaLenteCreate(BaseModel):
    descripcion: str

class MateriaLenteUpdate(BaseModel):
    descripcion: str | None = None

class MateriaLenteOut(BaseModel):
    id: int
    descripcion: str

    class Config:
        from_attributes = True