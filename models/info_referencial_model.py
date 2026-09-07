from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database.database import Base
from pydantic import BaseModel
from datetime import datetime

class InfoReferencial(Base):
    __tablename__ = "info_referencial"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow, nullable=False)

    tipo_referencia = Column(String(100), nullable=True)
    notas = Column(String(500), nullable=True)

    refraccion_od_esfera = Column(String(20), nullable=True)
    refraccion_od_cilindro = Column(String(20), nullable=True)
    refraccion_od_eje = Column(String(20), nullable=True)
    refraccion_od_adicion = Column(String(20), nullable=True)
    refraccion_od_av = Column(String(20), nullable=True)
    refraccion_od_dnp = Column(String(20), nullable=True)
    refraccion_od_prisma = Column(String(20), nullable=True)

    refraccion_oi_esfera = Column(String(20), nullable=True)
    refraccion_oi_cilindro = Column(String(20), nullable=True)
    refraccion_oi_eje = Column(String(20), nullable=True)
    refraccion_oi_adicion = Column(String(20), nullable=True)
    refraccion_oi_av = Column(String(20), nullable=True)
    refraccion_oi_dnp = Column(String(20), nullable=True)
    refraccion_oi_prisma = Column(String(20), nullable=True)

    refraccion_di_c = Column(String(20), nullable=True)
    refraccion_di_l = Column(String(20), nullable=True)

    hidrofilico_od_esfera = Column(String(20), nullable=True)
    hidrofilico_od_cilindro = Column(String(20), nullable=True)
    hidrofilico_od_eje = Column(String(20), nullable=True)
    hidrofilico_oi_esfera = Column(String(20), nullable=True)
    hidrofilico_oi_cilindro = Column(String(20), nullable=True)
    hidrofilico_oi_eje = Column(String(20), nullable=True)

    rigido_od_cb = Column(String(20), nullable=True)
    rigido_od_rx = Column(String(20), nullable=True)
    rigido_od_diam = Column(String(20), nullable=True)
    rigido_oi_cb = Column(String(20), nullable=True)
    rigido_oi_rx = Column(String(20), nullable=True)
    rigido_oi_diam = Column(String(20), nullable=True)
    rigido_material = Column(String(100), nullable=True)

    medidas_altura = Column(String(20), nullable=True)
    medidas_a = Column(String(20), nullable=True)
    medidas_ed = Column(String(20), nullable=True)
    medidas_b = Column(String(20), nullable=True)
    medidas_dbl = Column(String(20), nullable=True)

    esferico = Column(Boolean, default=False, nullable=False)
    torico = Column(Boolean, default=False, nullable=False)
    gp = Column(Boolean, default=False, nullable=False)
    con_conocimiento_paciente = Column(Boolean, default=False, nullable=False)

    motivo = Column(String(255), nullable=True)
    optometrista = Column(String(150), nullable=True)

    paciente = relationship("Paciente", backref="info_referencial")
    cliente = relationship("Cliente", backref="info_referencial")


class InfoReferencialCreate(BaseModel):
    cliente_id: int
    paciente_id: int
    tipo_referencia: str | None = None
    notas: str | None = None

    refraccion_od_esfera: str | None = None
    refraccion_od_cilindro: str | None = None
    refraccion_od_eje: str | None = None
    refraccion_od_adicion: str | None = None
    refraccion_od_av: str | None = None
    refraccion_od_dnp: str | None = None
    refraccion_od_prisma: str | None = None

    refraccion_oi_esfera: str | None = None
    refraccion_oi_cilindro: str | None = None
    refraccion_oi_eje: str | None = None
    refraccion_oi_adicion: str | None = None
    refraccion_oi_av: str | None = None
    refraccion_oi_dnp: str | None = None
    refraccion_oi_prisma: str | None = None

    refraccion_di_c: str | None = None
    refraccion_di_l: str | None = None

    hidrofilico_od_esfera: str | None = None
    hidrofilico_od_cilindro: str | None = None
    hidrofilico_od_eje: str | None = None
    hidrofilico_oi_esfera: str | None = None
    hidrofilico_oi_cilindro: str | None = None
    hidrofilico_oi_eje: str | None = None

    rigido_od_cb: str | None = None
    rigido_od_rx: str | None = None
    rigido_od_diam: str | None = None
    rigido_oi_cb: str | None = None
    rigido_oi_rx: str | None = None
    rigido_oi_diam: str | None = None
    rigido_material: str | None = None

    medidas_altura: str | None = None
    medidas_a: str | None = None
    medidas_ed: str | None = None
    medidas_b: str | None = None
    medidas_dbl: str | None = None

    esferico: bool | None = None
    torico: bool | None = None
    gp: bool | None = None
    con_conocimiento_paciente: bool | None = None

    motivo: str | None = None
    optometrista: str | None = None


class InfoReferencialUpdate(BaseModel):
    tipo_referencia: str | None = None
    notas: str | None = None

    refraccion_od_esfera: str | None = None
    refraccion_od_cilindro: str | None = None
    refraccion_od_eje: str | None = None
    refraccion_od_adicion: str | None = None
    refraccion_od_av: str | None = None
    refraccion_od_dnp: str | None = None
    refraccion_od_prisma: str | None = None

    refraccion_oi_esfera: str | None = None
    refraccion_oi_cilindro: str | None = None
    refraccion_oi_eje: str | None = None
    refraccion_oi_adicion: str | None = None
    refraccion_oi_av: str | None = None
    refraccion_oi_dnp: str | None = None
    refraccion_oi_prisma: str | None = None

    refraccion_di_c: str | None = None
    refraccion_di_l: str | None = None

    hidrofilico_od_esfera: str | None = None
    hidrofilico_od_cilindro: str | None = None
    hidrofilico_od_eje: str | None = None
    hidrofilico_oi_esfera: str | None = None
    hidrofilico_oi_cilindro: str | None = None
    hidrofilico_oi_eje: str | None = None

    rigido_od_cb: str | None = None
    rigido_od_rx: str | None = None
    rigido_od_diam: str | None = None
    rigido_oi_cb: str | None = None
    rigido_oi_rx: str | None = None
    rigido_oi_diam: str | None = None
    rigido_material: str | None = None

    medidas_altura: str | None = None
    medidas_a: str | None = None
    medidas_ed: str | None = None
    medidas_b: str | None = None
    medidas_dbl: str | None = None

    esferico: bool | None = None
    torico: bool | None = None
    gp: bool | None = None
    con_conocimiento_paciente: bool | None = None

    motivo: str | None = None
    optometrista: str | None = None


class InfoReferencialOut(BaseModel):
    id: int
    cliente_id: int
    paciente_id: int
    fecha: datetime
    tipo_referencia: str | None = None
    notas: str | None = None

    refraccion_od_esfera: str | None = None
    refraccion_od_cilindro: str | None = None
    refraccion_od_eje: str | None = None
    refraccion_od_adicion: str | None = None
    refraccion_od_av: str | None = None
    refraccion_od_dnp: str | None = None
    refraccion_od_prisma: str | None = None

    refraccion_oi_esfera: str | None = None
    refraccion_oi_cilindro: str | None = None
    refraccion_oi_eje: str | None = None
    refraccion_oi_adicion: str | None = None
    refraccion_oi_av: str | None = None
    refraccion_oi_dnp: str | None = None
    refraccion_oi_prisma: str | None = None

    refraccion_di_c: str | None = None
    refraccion_di_l: str | None = None

    hidrofilico_od_esfera: str | None = None
    hidrofilico_od_cilindro: str | None = None
    hidrofilico_od_eje: str | None = None
    hidrofilico_oi_esfera: str | None = None
    hidrofilico_oi_cilindro: str | None = None
    hidrofilico_oi_eje: str | None = None

    rigido_od_cb: str | None = None
    rigido_od_rx: str | None = None
    rigido_od_diam: str | None = None
    rigido_oi_cb: str | None = None
    rigido_oi_rx: str | None = None
    rigido_oi_diam: str | None = None
    rigido_material: str | None = None

    medidas_altura: str | None = None
    medidas_a: str | None = None
    medidas_ed: str | None = None
    medidas_b: str | None = None
    medidas_dbl: str | None = None

    esferico: bool
    torico: bool
    gp: bool
    con_conocimiento_paciente: bool

    motivo: str | None = None
    optometrista: str | None = None

    class Config:
        from_attributes = True