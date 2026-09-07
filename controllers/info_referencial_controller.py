from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.info_referencial_model import InfoReferencial, InfoReferencialCreate, InfoReferencialUpdate, InfoReferencialOut
from models.pacientes_model import Paciente
from models.clientes_model import Cliente

router = APIRouter(prefix="/info-referencial", tags=["Info Referencial"], dependencies=[Depends(get_current_user)])


@router.post("/create", response_model=InfoReferencialOut)
async def create_info_referencial(info: InfoReferencialCreate, db: AsyncSession = Depends(get_db)):
    try:
        cliente_result = await db.execute(select(Cliente).where(Cliente.id == info.cliente_id))
        if not cliente_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        paciente_result = await db.execute(select(Paciente).where(Paciente.id == info.paciente_id))
        if not paciente_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        new_info = InfoReferencial(**info.model_dump())

        db.add(new_info)
        await db.commit()
        await db.refresh(new_info)
        return new_info
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear info referencial: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/all", response_model=list[InfoReferencialOut])
async def get_all_info_referencial(db: AsyncSession = Depends(get_db)):
    try:
        query = select(InfoReferencial)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener info referencial: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/paciente/{paciente_id}", response_model=list[InfoReferencialOut])
async def get_info_referencial_by_paciente(paciente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(InfoReferencial).where(InfoReferencial.paciente_id == paciente_id)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener info referencial del paciente: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/cliente/{cliente_id}", response_model=list[InfoReferencialOut])
async def get_info_referencial_by_cliente(cliente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(InfoReferencial).where(InfoReferencial.cliente_id == cliente_id)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener info referencial del cliente: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/paciente/{paciente_id}/fecha/{fecha}", response_model=list[InfoReferencialOut])
async def get_info_referencial_by_paciente_y_fecha(paciente_id: int, fecha: date, db: AsyncSession = Depends(get_db)):
    try:
        inicio = datetime.combine(fecha, datetime.min.time())
        fin = inicio + timedelta(days=1)

        query = select(InfoReferencial).where(
            InfoReferencial.paciente_id == paciente_id,
            InfoReferencial.fecha >= inicio,
            InfoReferencial.fecha < fin
        )
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener info referencial por paciente y fecha: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/{info_id}", response_model=InfoReferencialOut)
async def get_info_referencial(info_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(InfoReferencial).where(InfoReferencial.id == info_id)
        result = await db.execute(query)
        info = result.scalar_one_or_none()

        if not info:
            raise HTTPException(status_code=404, detail="Info referencial no encontrada")

        return info
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener info referencial: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/update/{info_id}", response_model=InfoReferencialOut)
async def update_info_referencial(info_id: int, info_update: InfoReferencialUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(InfoReferencial).where(InfoReferencial.id == info_id)
        result = await db.execute(query)
        info = result.scalar_one_or_none()

        if not info:
            raise HTTPException(status_code=404, detail="Info referencial no encontrada")

        # Actualizar solo los campos enviados
        update_data = info_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(info, field, value)

        db.add(info)
        await db.commit()
        await db.refresh(info)
        return info
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar info referencial: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.delete("/delete/{info_id}")
async def delete_info_referencial(info_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(InfoReferencial).where(InfoReferencial.id == info_id)
        result = await db.execute(query)
        info = result.scalar_one_or_none()

        if not info:
            raise HTTPException(status_code=404, detail="Info referencial no encontrada")

        await db.delete(info)
        await db.commit()
        return {"message": "Info referencial eliminada correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar info referencial: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
