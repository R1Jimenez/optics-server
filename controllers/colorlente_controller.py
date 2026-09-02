from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.colorlente_model import ColorLente, ColorLenteCreate, ColorLenteUpdate, ColorLenteOut

router = APIRouter(prefix="/colorlente", tags=["Color de Lente"], dependencies=[Depends(get_current_user)])


@router.post('/create', response_model=ColorLenteOut)
async def create_colorlente(colorlente: ColorLenteCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ColorLente).where(ColorLente.descripcion == colorlente.descripcion)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Este color de lente ya existe")

        new_colorlente = ColorLente(descripcion=colorlente.descripcion)
        db.add(new_colorlente)
        await db.commit()
        await db.refresh(new_colorlente)
        return new_colorlente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[ColorLenteOut])
async def get_all_colorlente(db: AsyncSession = Depends(get_db)):
    try:
        query = select(ColorLente)
        result = await db.execute(query)
        colorlentes = result.scalars().all()
        return colorlentes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{colorlente_id}", response_model=ColorLenteOut)
async def get_colorlente(colorlente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ColorLente).where(ColorLente.id == colorlente_id)
        result = await db.execute(query)
        colorlente = result.scalar_one_or_none()
        if not colorlente:
            raise HTTPException(status_code=404, detail="Color de lente no encontrado")
        return colorlente
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{colorlente_id}", response_model=ColorLenteOut)
async def update_colorlente(colorlente_id: int, colorlente_update: ColorLenteUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ColorLente).where(ColorLente.id == colorlente_id)
        result = await db.execute(query)
        colorlente = result.scalar_one_or_none()
        if not colorlente:
            raise HTTPException(status_code=404, detail="Color de lente no encontrado")

        if colorlente_update.descripcion is not None:
            dup_query = select(ColorLente).where(
                ColorLente.descripcion == colorlente_update.descripcion,
                ColorLente.id != colorlente_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otro color de lente con esa descripción")

        for key, value in colorlente_update.model_dump(exclude_unset=True).items():
            setattr(colorlente, key, value)

        db.add(colorlente)
        await db.commit()
        await db.refresh(colorlente)
        return colorlente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{colorlente_id}")
async def delete_colorlente(colorlente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ColorLente).where(ColorLente.id == colorlente_id)
        result = await db.execute(query)
        colorlente = result.scalar_one_or_none()
        if not colorlente:
            raise HTTPException(status_code=404, detail="Color de lente no encontrado")

        await db.delete(colorlente)
        await db.commit()
        return {"detail": "Color de lente eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))