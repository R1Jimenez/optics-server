from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.database import get_db
from middleware.auth import get_current_user
from models.users_model import User
from models.conexiones_model import (
    HistorialConexion, ConexionOut, ConexionesPaginaOut, TipoConexion, TIPO_SALIDA
)

router = APIRouter(prefix="/conexiones", tags=["Historial de conexiones"], dependencies=[Depends(get_current_user)])


def _a_utc_naive(fecha: datetime) -> datetime:
    # las fechas se guardan en UTC sin zona horaria
    if fecha.tzinfo is None:
        return fecha
    return fecha.astimezone(timezone.utc).replace(tzinfo=None)


async def registrar_conexion(db: AsyncSession, user: User, tipo: str) -> HistorialConexion:
    conexion = HistorialConexion(
        user_id=user.id,
        usuario=user.usuario,
        nombre=f"{user.nombres} {user.apellidos}".strip(),
        tipo=tipo,
    )
    db.add(conexion)
    await db.commit()
    await db.refresh(conexion)
    return conexion


@router.post("/salida", response_model=ConexionOut)
async def registrar_salida(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        user = await db.get(User, current_user.get("id"))
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        return await registrar_conexion(db, user, TIPO_SALIDA)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al registrar salida: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/all", response_model=ConexionesPaginaOut)
async def listar_conexiones(
    usuario_id: int | None = Query(None),
    tipo: TipoConexion | None = Query(None),
    desde: datetime | None = Query(None),
    hasta: datetime | None = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(HistorialConexion)
        if usuario_id is not None:
            query = query.where(HistorialConexion.user_id == usuario_id)
        if tipo:
            query = query.where(HistorialConexion.tipo == tipo)
        if desde is not None:
            query = query.where(HistorialConexion.fecha >= _a_utc_naive(desde))
        if hasta is not None:
            query = query.where(HistorialConexion.fecha < _a_utc_naive(hasta))

        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(
            query.order_by(HistorialConexion.fecha.desc(), HistorialConexion.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        items = [ConexionOut.model_validate(c) for c in result.scalars().all()]
        return ConexionesPaginaOut(total=total, pagina=pagina, por_pagina=por_pagina, items=items)
    except Exception as e:
        print(f"Error al listar conexiones: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
