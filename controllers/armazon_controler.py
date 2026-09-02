from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.armazon_model import Armazon, ArmazonCreate, ArmazonUpdate, ArmazonOut

router = APIRouter(prefix="/armazones", tags=["Armazones"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=ArmazonOut)
async def create_armazon(armazon: ArmazonCreate, db: AsyncSession = Depends(get_db)):

    try:
        existingarmazon = select(Armazon).where(Armazon.marca == armazon.marca)
        result = await db.execute(existingarmazon)
        existing_armazon = result.scalars().first()

        if existing_armazon:
            raise HTTPException(status_code=400, detail="Este armazón ya existe")

        new_armazon = Armazon(
            marca = armazon.marca,
            precio = armazon.precio
        )

        db.add(new_armazon)
        await db.commit()
        await db.refresh(new_armazon)
        return new_armazon
    
    except Exception as e:
        await db.rollback()
        print(f"Error al crear armazón: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[ArmazonOut])
async def get_all_armazones(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Armazon)
        result = await db.execute(query)
        armazones = result.scalars().all()
        return armazones
    
    except Exception as e:
        print(f"Error al obtener armazones: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{armazon_id}", response_model=ArmazonOut)
async def get_armazon(armazon_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Armazon).where(Armazon.id == armazon_id)
        result = await db.execute(query)
        armazon = result.scalar_one_or_none()

        if not armazon:
            raise HTTPException(
                status_code=404,
                detail="Armazón no encontrado o inexistente"
            )
        
        return armazon
    
    except Exception as e:
        print(f"Error al obtener armazón: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{armazon_id}", response_model=ArmazonOut)
async def update_armazon(armazon_id: int, armazon_update: ArmazonUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Armazon).where(Armazon.id == armazon_id)
        result = await db.execute(query)
        armazon_result = result.scalar_one_or_none()

        if not armazon_result:
            raise HTTPException(
                status_code=404,
                detail="Armazón no encontrado o inexistente"
            )
        
        update_data = armazon_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se proporcionaron datos para actualizar"
            )
        
        if "marca" in update_data:
            existing_armazon_query = select(Armazon).where(Armazon.marca == update_data.get("marca"), Armazon.id != armazon_id)
            existing_armazon_result = await db.execute(existing_armazon_query)
            existing_armazon = existing_armazon_result.scalar_one_or_none()

            if existing_armazon:
                raise HTTPException(
                    status_code=400,
                    detail="El armazón con esta marca ya existe"
                )
        
        for key, value in update_data.items():
            setattr(armazon_result, key, value)
        
        db.add(armazon_result)
        await db.commit()
        await db.refresh(armazon_result)
        return armazon_result
    
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar armazón: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{armazon_id}")
async def delete_armazon(armazon_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Armazon).where(Armazon.id == armazon_id)
        result = await db.execute(query)
        armazon_result = result.scalar_one_or_none()

        if not armazon_result:
            raise HTTPException(
                status_code=404,
                detail="Armazón no encontrado o inexistente"
            )
        
        await db.delete(armazon_result)
        await db.commit()
        return {"detail": "Armazón eliminado correctamente"}
    
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar armazón: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )