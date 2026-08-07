from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class MarcaProd(Base):
    __tablename__ = "MarcaProd"

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(50), nullable=False)

class MarcaProdCreate(BaseModel):
    descripcion: str

class MarcaProdUpdate(BaseModel):
    descripcion: str | None = None

class MarcaProdOut(BaseModel):
    id: int
    descripcion: str

    class Config:
        from_attributes = True