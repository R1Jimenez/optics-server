from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class TipoLente(Base):
    __tablename__ = "TipoLente"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(50), nullable=False)

class TipoLenteCreate(BaseModel):
    descripcion: str

class TipoLenteUpdate(BaseModel):
    descripcion: str | None = None

class TipoLenteOut(BaseModel):
    id: int
    descripcion: str

    class Config:
        from_attributes = True