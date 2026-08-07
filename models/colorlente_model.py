from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class ColorLente(Base):
    __tablename__ = "ColorLente"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(50), nullable=False)

class ColorLenteCreate(BaseModel):
    descripcion: str

class ColorLenteUpdate(BaseModel):
    descripcion: str | None = None

class ColorLenteOut(BaseModel):
    id: int
    descripcion: str

    class Config:
        from_attributes = True