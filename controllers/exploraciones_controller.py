from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.exploraciones_model import Exploraciones, ExploracionCreate, ExploracionUpdate, ExploracionOut
from models.pacientes_model import Paciente

router = APIRouter(prefix="/exploraciones", tags=["Exploraciones"], dependencies=[Depends(get_current_user)])


@router.post("/create", response_model=ExploracionOut)
async def create_exploracion(exploracion: ExploracionCreate, db: AsyncSession = Depends(get_db)):
    try:
        paciente_result = await db.execute(select(Paciente).where(Paciente.id == exploracion.paciente_id))
        if not paciente_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        new_exploracion = Exploraciones(
            paciente_id=exploracion.paciente_id,
            conjuntiva_parpado=exploracion.conjuntiva_parpado,
            vias_lacrimal=exploracion.vias_lacrimal,
            pterigion=exploracion.pterigion,
            agudeza_visual=exploracion.agudeza_visual,
            bicromatica=exploracion.bicromatica,
            esquiascopia=exploracion.esquiascopia,
            oftalmoscopia=exploracion.oftalmoscopia,
            queratometria_od=exploracion.queratometria_od,
            queratometria_oi=exploracion.queratometria_oi,
            lectura_refractometro_od=exploracion.lectura_refractometro_od,
            lectura_refractometro_oi=exploracion.lectura_refractometro_oi,
            lectura_graduacion_od=exploracion.lectura_graduacion_od,
            lectura_graduacion_oi=exploracion.lectura_graduacion_oi,
            reflectividad=exploracion.reflectividad,
            motilidad=exploracion.motilidad,
            av_con_od=exploracion.av_con_od,
            av_con_oi=exploracion.av_con_oi,
            av_sin_od=exploracion.av_sin_od,
            av_sin_oi=exploracion.av_sin_oi
        )

        db.add(new_exploracion)
        await db.commit()
        await db.refresh(new_exploracion)
        return new_exploracion
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear exploracion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/all", response_model=list[ExploracionOut])
async def get_all_exploraciones(db: AsyncSession = Depends(get_db)):
    try:
        query = select(Exploraciones)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener exploraciones: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/paciente/{paciente_id}", response_model=list[ExploracionOut])
async def get_exploraciones_by_paciente(paciente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Exploraciones).where(Exploraciones.paciente_id == paciente_id)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener exploraciones del paciente: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/paciente/{paciente_id}/fecha/{fecha}", response_model=list[ExploracionOut])
async def get_exploraciones_by_paciente_y_fecha(paciente_id: int, fecha: date, db: AsyncSession = Depends(get_db)):
    try:
        inicio = datetime.combine(fecha, datetime.min.time())
        fin = inicio + timedelta(days=1)

        query = select(Exploraciones).where(
            Exploraciones.paciente_id == paciente_id,
            Exploraciones.fecha >= inicio,
            Exploraciones.fecha < fin
        )
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        print(f"Error al obtener exploraciones por paciente y fecha: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/{exploracion_id}", response_model=ExploracionOut)
async def get_exploracion(exploracion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Exploraciones).where(Exploraciones.id == exploracion_id)
        result = await db.execute(query)
        exploracion = result.scalar_one_or_none()

        if not exploracion:
            raise HTTPException(status_code=404, detail="Exploracion no encontrada")

        return exploracion
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener exploracion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/update/{exploracion_id}", response_model=ExploracionOut)
async def update_exploracion(exploracion_id: int, exploracion_update: ExploracionUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Exploraciones).where(Exploraciones.id == exploracion_id)
        result = await db.execute(query)
        exploracion = result.scalar_one_or_none()

        if not exploracion:
            raise HTTPException(status_code=404, detail="Exploracion no encontrada")

        # Actualizar solo los campos enviados
        update_data = exploracion_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(exploracion, field, value)

        db.add(exploracion)
        await db.commit()
        await db.refresh(exploracion)
        return exploracion
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar exploracion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.delete("/delete/{exploracion_id}")
async def delete_exploracion(exploracion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Exploraciones).where(Exploraciones.id == exploracion_id)
        result = await db.execute(query)
        exploracion = result.scalar_one_or_none()

        if not exploracion:
            raise HTTPException(status_code=404, detail="Exploracion no encontrada")

        await db.delete(exploracion)
        await db.commit()
        return {"message": "Exploracion eliminada correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar exploracion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
