from sqlalchemy import ARRAY, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel, EmailStr
from datetime import datetime
from models.user_roles_model import UserRoleOut

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index = True)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    usuario = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    telefono = Column(String(30), nullable=False)
    Sucursal = Column(Integer, nullable=False)
    sucursal_acces = Column(ARRAY(Integer), default=list, nullable=False)
    roles = Column(ARRAY(Integer), default=list, nullable=False)
    hashed_password = Column(String(255), nullable=False)

class UserSignUp (BaseModel):
    nombres: str
    apellidos: str
    usuario: str
    email: EmailStr
    telefono: str
    Sucursal: int
    sucursal_acces: list[int]
    roles: list[int]
    password: str

class UserLogin(BaseModel):
    usuario: str
    password: str


class UserUpdate (BaseModel):
    nombres: str | None = None
    apellidos: str | None = None
    usuario: str | None = None
    email: EmailStr | None = None
    telefono: str | None = None
    Sucursal: int | None = None
    sucursal_acces: list[int] | None = None
    roles: list[int] | None = None
    password: str | None = None

class UserOut (BaseModel):
    id: int
    nombres: str
    apellidos: str
    usuario: str
    email: EmailStr
    telefono: str
    Sucursal: str
    sucursal_acces: list[str]
    roles: list[int]

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut