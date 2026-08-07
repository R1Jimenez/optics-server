from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class ModeloProd(Base):
    __tablename__ = "ModeloProd"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(50), nullable=False)

class ModeloProdCreate(BaseModel):
    descripcion: str

class ModeloProdUpdate(BaseModel):
    descripcion: str | None = None

class ModeloProdOut(BaseModel):
    id: int
    descripcion: str

    class Config:
        from_attributes = True