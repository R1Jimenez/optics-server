from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.atributos_model import Atributo, AtributoCreate, AtributoUpdate, AtributoOut

router = APIRouter(prefix="/atributos", tags=["Atributos"])

@router.post("/create", response_model=AtributoOut)
async def create_atributo(atributo: AtributoCreate, db: AsyncSession = Depends(get_db)):

    try:
        existingatributo = select(Atributo).where(Atributo.atributo == atributo.atributo)
        result = await db.execute(existingatributo)
        existing_atributo = result.scalars().first()

        if existing_atributo:
            raise HTTPException(status_code=400, detail="Este atributo ya existe")
        
        new_atributo = Atributo(
            longitud = atributo.longitud,
            atributo = atributo.atributo
        )

        db.add(new_atributo)
        await db.commit()
        await db.refresh(new_atributo)
        return new_atributo
    
    except Exception as e:
        await db.rollback()
        print(f"Error al crear atributo: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[AtributoOut])
async def get_all_atributos(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Atributo)
        result = await db.execute(query)
        atributos = result.scalars().all()
        return atributos
    
    except Exception as e:
        print(f"Error al obtener atributos: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{atributo_id}", response_model=AtributoOut)
async def update_atributo(atributo_id: int, atributo_update: AtributoUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Atributo).where(Atributo.id == atributo_id)
        result = await db.execute(query)
        atributo_result = result.scalar_one_or_none()

        if not atributo_result:
            raise HTTPException(
                status_code=404,
                detail="Atributo no encontrado o inexistente"
            )
        
        update_data = atributo_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se proporcionaron datos para actualizar"
            )
        
        if "atributo" in update_data:
            existing_atributo_query = select(Atributo).where(Atributo.atributo == update_data.get("atributo"), Atributo.id != atributo_id)
            existing_atributo_result = await db.execute(existing_atributo_query)
            existing_atributo = existing_atributo_result.scalar_one_or_none()

            if existing_atributo:
                raise HTTPException(
                    status_code=400,
                    detail="El atributo ya existe"
                )
        
        for key, value in update_data.items():
            setattr(atributo_result, key, value)
        
        db.add(atributo_result)
        await db.commit()
        await db.refresh(atributo_result)
        return atributo_result
    
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar atributo: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{atributo_id}")
async def delete_atributo(atributo_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Atributo).where(Atributo.id == atributo_id)
        result = await db.execute(query)
        atributo_result = result.scalar_one_or_none()

        if not atributo_result:
            raise HTTPException(
                status_code=404,
                detail="Atributo no encontrado o inexistente"
            )
        
        await db.delete(atributo_result)
        await db.commit()
        return {"detail": "Atributo eliminado correctamente"}
    
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar atributo: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )