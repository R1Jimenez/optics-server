from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel

class Orders(Base):
    __tablename__ = "generalorder"

    id = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, nullable=False)
    cliente_id = Column(Integer, nullable=False)
    order_id = Column(Integer, nullable=False)

class OrderCreate(BaseModel):
    id_user: int
    cliente_id: int
    order_id: int

class OrderOut(BaseModel):
    id: int
    id_user: int
    cliente_id: int
    order_id: int

    class Config:
        from_attributes = True
    