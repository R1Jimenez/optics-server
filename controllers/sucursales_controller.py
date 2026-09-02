from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.sucursales_model import Sucursal, SucursalCreate, SucursalUpdate, SucursalOut
from models.tipo_sucursal_model import tipoSucursal
from models.estado_sucursal_model import Estado_Sucursal

router = APIRouter(prefix="/sucursales", tags=["Sucursales"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=SucursalOut)
async def create_sucursal(sucursal: SucursalCreate, db: AsyncSession = Depends(get_db)):

    try:
        # Validar que tipo_sucursal_id existe
        tipo_query = select(tipoSucursal).where(tipoSucursal.id == sucursal.tipo_sucursal_id)
        tipo_result = await db.execute(tipo_query)
        tipo_exists = tipo_result.scalar_one_or_none()
        
        if not tipo_exists:
            raise HTTPException(
                status_code=400,
                detail=f"El tipo de sucursal con ID {sucursal.tipo_sucursal_id} no existe"
            )
        
        # Validar que estado_sucursal_id existe
        estado_query = select(Estado_Sucursal).where(Estado_Sucursal.id == sucursal.estado_sucursal_id)
        estado_result = await db.execute(estado_query)
        estado_exists = estado_result.scalar_one_or_none()
        
        if not estado_exists:
            raise HTTPException(
                status_code=400,
                detail=f"El estado de sucursal con ID {sucursal.estado_sucursal_id} no existe"
            )
        
        # Validar que la sucursal no exista
        existing_sucursal = select(Sucursal).where(Sucursal.sucursal == sucursal.sucursal)
        result = await db.execute(existing_sucursal)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="La sucursal ya existe"
            )
        
        # Crear nueva sucursal
        new_sucursal = Sucursal(
            sucursal = sucursal.sucursal,
            tipo_sucursal_id = sucursal.tipo_sucursal_id,
            dependencia = sucursal.dependencia,
            mondeda = sucursal.mondeda,
            razon_social = sucursal.razon_social,
            estado_sucursal_id = sucursal.estado_sucursal_id
        )

        db.add(new_sucursal)
        await db.commit()
        await db.refresh(new_sucursal)
        return new_sucursal
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[SucursalOut])
async def get_all_sucursales(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Sucursal).order_by(Sucursal.sucursal)
        result = await db.execute(query)
        sucursales = result.scalars().all()
        return sucursales
    
    except Exception as e:
        print(f"Error al obtener sucursales: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{sucursal_id}", response_model=SucursalOut)
async def get_sucursal(sucursal_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Sucursal).where(Sucursal.id == sucursal_id)
        result = await db.execute(query)
        sucursal = result.scalar_one_or_none()
        
        if not sucursal:
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada"
            )

        return sucursal
    
    except Exception as e:
        print(f"Error al obtener sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{sucursal_id}", response_model=SucursalOut)
async def update_sucursal(sucursal_id: int, sucursal_update: SucursalUpdate, db: AsyncSession = Depends(get_db)):

    try: 
        query = select(Sucursal).where(Sucursal.id == sucursal_id)
        result = await db.execute(query)

        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada"
            )
        
        update_data = sucursal_update.dict(exclude_unset=True) 

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se han proporcionado datos por actualizar"
            )

        tipo_query = select(tipoSucursal).where(tipoSucursal.id == update_data.get("tipo_sucursal_id", 0))
        tipo_result = await db.execute(tipo_query)

        if tipo_result.scalar_one_or_none() is None and "tipo_sucursal_id" in update_data:
            raise HTTPException(
                status_code=400,
                detail=f"El tipo de sucursal con ID {update_data['tipo_sucursal_id']} no existe"
            )
        
        estado_query = select(Estado_Sucursal).where(Estado_Sucursal.id == update_data.get("estado_sucursal_id", 0))
        estado_result = await db.execute(estado_query)

        if estado_result.scalar_one_or_none() is None and "estado_sucursal_id" in update_data:
            raise HTTPException(
                status_code=400,
                detail=f"El estado de sucursal con ID {update_data['estado_sucursal_id']} no existe"
            )
        
        # Verificar si el nuevo nombre de sucursal ya existe (si se está actualizando el nombre)
        if "sucursal" in update_data:
            nombre_query = select(Sucursal).where(
                Sucursal.sucursal == update_data["sucursal"],
                Sucursal.id != sucursal_id
            )
            nombre_result = await db.execute(nombre_query)
            if nombre_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe una sucursal con ese nombre"
                )
        
        # Obtener la sucursal nuevamente para actualizar
        query = select(Sucursal).where(Sucursal.id == sucursal_id)
        result = await db.execute(query)
        existing_sucursal = result.scalar_one_or_none()
        
        # Actualizar campos
        for key, value in update_data.items():
            setattr(existing_sucursal, key, value)
        
        await db.commit()
        await db.refresh(existing_sucursal)
        return existing_sucursal
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@router.delete("/delete/{sucursal_id}")
async def delete_sucursal(sucursal_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Sucursal).where(Sucursal.id == sucursal_id)
        result = await db.execute(query)
        existing_sucursal = result.scalar_one_or_none()

        if not existing_sucursal:
            raise HTTPException(
                status_code=404,
                detail="Sucursal no encontrada"
            )

        await db.delete(existing_sucursal)
        await db.commit()

        return {"message": "Sucursal eliminada correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
