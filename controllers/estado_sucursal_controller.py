from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.estado_sucursal_model import Estado_Sucursal, EstadoSucursalCreate, EstadoSucursalUpdate, EstadoSucursalOut
from typing import List

router = APIRouter(prefix="/estado_sucursal", tags=["Estado_Sucursal"], dependencies=[Depends(get_current_user)])

# CREATE - Crear estado de sucursal
@router.post("/create", response_model=EstadoSucursalOut)
async def create_estado_sucursal(estado_sucursal: EstadoSucursalCreate, db: AsyncSession = Depends(get_db)):
    try:
        # Verificar si ya existe
        existing_state = select(Estado_Sucursal).where(Estado_Sucursal.estado == estado_sucursal.estado)
        result = await db.execute(existing_state)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="El estado de sucursal ya existe"
            )

        # Crear nuevo estado
        new_estado = Estado_Sucursal(
            estado=estado_sucursal.estado
        )
        db.add(new_estado)
        await db.commit()
        await db.refresh(new_estado)
        return new_estado
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear estado de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

# READ - Obtener todos los estados
@router.get("/all", response_model=List[EstadoSucursalOut])
async def get_all_estados(db: AsyncSession = Depends(get_db)):
    try:
        query = select(Estado_Sucursal)
        result = await db.execute(query)
        estados = result.scalars().all()
        return estados
    
    except Exception as e:
        print(f"Error al obtener estados: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

# READ - Obtener un estado por ID
@router.get("/{estado_id}", response_model=EstadoSucursalOut)
async def get_estado_sucursal(estado_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Estado_Sucursal).where(Estado_Sucursal.id == estado_id)
        result = await db.execute(query)
        estado = result.scalar_one_or_none()

        if not estado:
            raise HTTPException(
                status_code=404,
                detail="Estado de sucursal no encontrado"
            )

        return estado
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener estado: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

# UPDATE - Actualizar estado de sucursal
@router.post("/update/{estado_id}", response_model=EstadoSucursalOut)
async def update_estado_sucursal(estado_id: int, updates: EstadoSucursalUpdate, db: AsyncSession = Depends(get_db)):
    try:
        # Buscar el estado
        query = select(Estado_Sucursal).where(Estado_Sucursal.id == estado_id)
        result = await db.execute(query)
        existing_estado = result.scalar_one_or_none()

        if not existing_estado:
            raise HTTPException(
                status_code=404,
                detail="Estado de sucursal no encontrado"
            )

        # Obtener datos a actualizar
        update_data = updates.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se han proporcionado datos por actualizar"
            )

        # Verificar si el nuevo nombre ya existe
        if "estado" in update_data:
            check_query = select(Estado_Sucursal).where(
                Estado_Sucursal.estado == update_data["estado"],
                Estado_Sucursal.id != estado_id
            )
            check_result = await db.execute(check_query)
            if check_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="El estado de sucursal ya existe"
                )

        # Actualizar campos
        for key, value in update_data.items():
            setattr(existing_estado, key, value)

        await db.commit()
        await db.refresh(existing_estado)
        return existing_estado
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar estado de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

# DELETE - Eliminar estado de sucursal
@router.delete("/delete/{estado_id}")
async def delete_estado_sucursal(estado_id: int, db: AsyncSession = Depends(get_db)):
    try:
        # Buscar el estado
        query = select(Estado_Sucursal).where(Estado_Sucursal.id == estado_id)
        result = await db.execute(query)
        existing_estado = result.scalar_one_or_none()

        if not existing_estado:
            raise HTTPException(
                status_code=404,
                detail="Estado de sucursal no encontrado"
            )

        # Eliminar físicamente (no soft delete)
        await db.delete(existing_estado)
        await db.commit()

        return {"message": "Estado de sucursal eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar estado de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )