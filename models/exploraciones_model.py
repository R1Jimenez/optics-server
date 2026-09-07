from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel
from datetime import datetime

class Exploraciones(Base):
    __tablename__ = "exploraciones"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)
    conjuntiva_parpado = Column(String(255), nullable=True)
    vias_lacrimal = Column(String(255), nullable=True)
    pterigion = Column(String(255), nullable=True)
    agudeza_visual = Column(String(255), nullable=True)
    bicromatica = Column(String(255), nullable=True)
    esquiascopia = Column(String(255), nullable=True)
    oftalmoscopia = Column(String(255), nullable=True)
    queratometria_od = Column(String(255), nullable=True)
    queratometria_oi = Column(String(255), nullable=True)
    lectura_refractometro_od = Column(String(255), nullable=True)
    lectura_refractometro_oi = Column(String(255), nullable=True)
    lectura_graduacion_od = Column(String(255), nullable=True)
    lectura_graduacion_oi = Column(String(255), nullable=True)
    reflectividad = Column(String(255), nullable=True)
    motilidad = Column(String(255), nullable=True)
    av_con_od = Column(String(255), nullable=True)
    av_con_oi = Column(String(255), nullable=True)
    av_sin_od = Column(String(255), nullable=True)
    av_sin_oi = Column(String(255), nullable=True)

    paciente = relationship("Paciente", backref="exploraciones")
    cliente = relationship("Cliente", backref="exploraciones")


class ExploracionCreate(BaseModel):
    cliente_id: int | None = None
    paciente_id: int
    conjuntiva_parpado: str | None = None
    vias_lacrimal: str | None = None
    pterigion: str | None = None
    agudeza_visual: str | None = None
    bicromatica: str | None = None
    esquiascopia: str | None = None
    oftalmoscopia: str | None = None
    queratometria_od: str | None = None
    queratometria_oi: str | None = None
    lectura_refractometro_od: str | None = None
    lectura_refractometro_oi: str | None = None
    lectura_graduacion_od: str | None = None
    lectura_graduacion_oi: str | None = None
    reflectividad: str | None = None
    motilidad: str | None = None
    av_con_od: str | None = None
    av_con_oi: str | None = None
    av_sin_od: str | None = None
    av_sin_oi: str | None = None


class ExploracionUpdate(BaseModel):
    conjuntiva_parpado: str | None = None
    vias_lacrimal: str | None = None
    pterigion: str | None = None
    agudeza_visual: str | None = None
    bicromatica: str | None = None
    esquiascopia: str | None = None
    oftalmoscopia: str | None = None
    queratometria_od: str | None = None
    queratometria_oi: str | None = None
    lectura_refractometro_od: str | None = None
    lectura_refractometro_oi: str | None = None
    lectura_graduacion_od: str | None = None
    lectura_graduacion_oi: str | None = None
    reflectividad: str | None = None
    motilidad: str | None = None
    av_con_od: str | None = None
    av_con_oi: str | None = None
    av_sin_od: str | None = None
    av_sin_oi: str | None = None


class ExploracionOut(BaseModel):
    id: int
    cliente_id: int | None = None
    paciente_id: int
    fecha: datetime
    conjuntiva_parpado: str | None = None
    vias_lacrimal: str | None = None
    pterigion: str | None = None
    agudeza_visual: str | None = None
    bicromatica: str | None = None
    esquiascopia: str | None = None
    oftalmoscopia: str | None = None
    queratometria_od: str | None = None
    queratometria_oi: str | None = None
    lectura_refractometro_od: str | None = None
    lectura_refractometro_oi: str | None = None
    lectura_graduacion_od: str | None = None
    lectura_graduacion_oi: str | None = None
    reflectividad: str | None = None
    motilidad: str | None = None
    av_con_od: str | None = None
    av_con_oi: str | None = None
    av_sin_od: str | None = None
    av_sin_oi: str | None = None

    class Config:
        from_attributes = True
