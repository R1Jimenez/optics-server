from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class RangoLente(Base):
    __tablename__ = "RangoLente"

    id = Column(Integer, primary_key=True, index=True)
    rango = Column(String(50), nullable=False)

class RangoLenteCreate(BaseModel):
    rango: str

class RangoLenteUpdate(BaseModel):
    rango: str | None = None

class RangoLenteOut(BaseModel):
    id: int
    rango: str

    class Config:
        from_attributes = True