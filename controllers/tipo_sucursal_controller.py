from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.tipo_sucursal_model import TipoSucursalOut, tipoSucursal, tipoSucursalCreate, tipoSucursalUpdate

router = APIRouter(prefix="/tipo_sucursal", tags=["Tipo_Sucursal"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=TipoSucursalOut)
async def create_tipo_sucursal(tipo_sucursal: tipoSucursalCreate, db: AsyncSession = Depends(get_db)):

    try:
        existing_type = select(tipoSucursal).where(tipoSucursal.tipo == tipo_sucursal.tipo)
        result = await db.execute(existing_type)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="El tipo de sucursal ya existe"
            )
        
        new_tipo = tipoSucursal(
            tipo = tipo_sucursal.tipo
        )

        db.add(new_tipo)
        await db.commit()
        await db.refresh(new_tipo)
        return new_tipo
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear tipo de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[TipoSucursalOut])
async def get_all_tipos(db: AsyncSession = Depends(get_db)):

    try:
        query = select(tipoSucursal)
        result = await db.execute(query)
        tipos = result.scalars().all()
        return tipos
    
    except Exception as e:
        print(f"Error al obtener tipos de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{tipo_id}", response_model=TipoSucursalOut)
async def get_tipo_sucursal(tipo_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(tipoSucursal).where(tipoSucursal.id == tipo_id)
        result = await db.execute(query)
        tipo = result.scalar_one_or_none()

        if not tipo:
            raise HTTPException(
                status_code=404,
                detail="Tipo de sucursal no encontrado"
            )
        
        return tipo
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener tipo de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{tipo_id}", response_model=TipoSucursalOut)
async def update_tipo_sucursal(tipo_id: int, updates: tipoSucursalUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(tipoSucursal).where(tipoSucursal.id == tipo_id)
        result = await db.execute(query)
        existing_tipo = result.scalar_one_or_none()

        if not existing_tipo:
            raise HTTPException(
                status_code=404,
                detail="Tipo de sucursal no encontrado"
            )
        
        update_data = updates.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se han proporcionado datos por actualizar"
            )
        
        if "tipo" in update_data:
            tipo_query = select(tipoSucursal).where(
                tipoSucursal.tipo == update_data["tipo"],
                tipoSucursal.id != tipo_id
            )
            check_result = await db.execute(tipo_query)
            if check_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="Este tipo de sucursal ya existe"
                )
            
        for key, value in update_data.items():
            setattr(existing_tipo, key, value)

        await db.commit()
        await db.refresh(existing_tipo)
        return existing_tipo
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar tipo de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{tipo_id}")
async def delete_tipo_sucursal(tipo_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(tipoSucursal).where(tipoSucursal.id == tipo_id)
        result = await db.execute(query)
        existing_tipo = result.scalar_one_or_none()

        if not existing_tipo:
            raise HTTPException(
                status_code=404,
                detail="Tipo de sucursal no encontrado"
            )
        
        await db.delete(existing_tipo)
        await db.commit()
        return {"detail": "Tipo de sucursal eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar tipo de sucursal: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )