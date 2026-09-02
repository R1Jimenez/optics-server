from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.servico_model import Servicio, ServicioCreate, ServicioUpdate, ServicioOut

router = APIRouter(prefix="/servicios", tags=["Servicios"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=ServicioOut)
async def create_servicio(servicio: ServicioCreate, db: AsyncSession = Depends(get_db)):

    try:
        existing_servicio = select(Servicio).where(Servicio.servicio == servicio.servicio)
        result = await db.execute(existing_servicio)
        existing_servicio_db = result.scalars().first()

        if existing_servicio_db:
            raise HTTPException(status_code=400, detail="Este servicio ya existe")

        new_servicio = Servicio(
            servicio = servicio.servicio,
            precio = servicio.precio
        )

        db.add(new_servicio)
        await db.commit()
        await db.refresh(new_servicio)
        return new_servicio
    
    except Exception as e:
        await db.rollback()
        print(f"Error al crear servicio: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[ServicioOut])
async def get_all_servicios(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Servicio)
        result = await db.execute(query)
        servicios = result.scalars().all()
        return servicios
    
    except Exception as e:
        print(f"Error al obtener servicios: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{servicio_id}", response_model=ServicioOut)
async def get_servicio(servicio_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Servicio).where(Servicio.id == servicio_id)
        result = await db.execute(query)
        servicio = result.scalar_one_or_none()

        if not servicio:
            raise HTTPException(
                status_code=404,
                detail="Servicio no encontrado o inexistente"
            )
        
        return servicio
    
    except Exception as e:
        print(f"Error al obtener servicio: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{servicio_id}", response_model=ServicioOut)
async def update_servicio(servicio_id: int, servicio_update: ServicioUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Servicio).where(Servicio.id == servicio_id)
        result = await db.execute(query)
        servicio_result = result.scalar_one_or_none()

        if not servicio_result:
            raise HTTPException(
                status_code=404,
                detail="Servicio no encontrado o inexistente"
            )
        
        update_data = servicio_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se proporcionaron datos para actualizar"
            )
        
        existing_servicio_query = select(Servicio).where(Servicio.servicio == update_data.get("servicio"), Servicio.id != servicio_id)
        existing_servicio_result = await db.execute(existing_servicio_query)
        existing_servicio = existing_servicio_result.scalar_one_or_none()

        if existing_servicio:
            raise HTTPException(
                status_code=400,
                detail="El servicio ya existe"
            )
        
        for key, value in update_data.items():
            setattr(servicio_result, key, value)
        
        db.add(servicio_result)
        await db.commit()
        await db.refresh(servicio_result)
        return servicio_result
    
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar servicio: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{servicio_id}")
async def delete_servicio(servicio_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Servicio).where(Servicio.id == servicio_id)
        result = await db.execute(query)
        servicio_result = result.scalar_one_or_none()

        if not servicio_result:
            raise HTTPException(
                status_code=404,
                detail="Servicio no encontrado o inexistente"
            )
        
        await db.delete(servicio_result)
        await db.commit()
        return {"detail": "Servicio eliminado correctamente"}
    
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar servicio: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )