from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Plazo(Base):
    __tablename__ = "plazo"

    id = Column(Integer, primary_key=True, index=True)
    plazo = Column(String(100), nullable=False)

class PlazoCreate(BaseModel):
    plazo: str

class PlazoUpdate(BaseModel):
    plazo: str | None = None

class PlazoOut(BaseModel):
    id: int
    plazo: str

    class Config:
        from_attributes = True