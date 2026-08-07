from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Atributo(Base):
    __tablename__= "atributos"

    id = Column(Integer, primary_key=True, index=True)
    longitud = Column(Integer, nullable=False)
    atributo = Column(String(100), nullable=False)

class AtributoCreate(BaseModel):
    longitud:int
    atributo:str

class AtributoUpdate(BaseModel):
    longitud: int | None = None
    atributo: str | None = None

class AtributoOut(BaseModel):
    id: int
    longitud: int
    atributo: str

    class Config:
        from_attributes = True