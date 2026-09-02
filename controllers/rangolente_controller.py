from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.rangolente_model import RangoLente, RangoLenteCreate, RangoLenteUpdate, RangoLenteOut

router = APIRouter(prefix="/rangolente", tags=["Rango de Lente"], dependencies=[Depends(get_current_user)])


@router.post('/create', response_model=RangoLenteOut)
async def create_rangolente(rangolente: RangoLenteCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(RangoLente).where(RangoLente.rango == rangolente.rango)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Este rango de lente ya existe")

        new_rangolente = RangoLente(rango=rangolente.rango)
        db.add(new_rangolente)
        await db.commit()
        await db.refresh(new_rangolente)
        return new_rangolente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[RangoLenteOut])
async def get_all_rangolente(db: AsyncSession = Depends(get_db)):
    try:
        query = select(RangoLente)
        result = await db.execute(query)
        rangolentes = result.scalars().all()
        return rangolentes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rangolente_id}", response_model=RangoLenteOut)
async def get_rangolente(rangolente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(RangoLente).where(RangoLente.id == rangolente_id)
        result = await db.execute(query)
        rangolente = result.scalar_one_or_none()
        if not rangolente:
            raise HTTPException(status_code=404, detail="Rango de lente no encontrado")
        return rangolente
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{rangolente_id}", response_model=RangoLenteOut)
async def update_rangolente(rangolente_id: int, rangolente_update: RangoLenteUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(RangoLente).where(RangoLente.id == rangolente_id)
        result = await db.execute(query)
        rangolente = result.scalar_one_or_none()
        if not rangolente:
            raise HTTPException(status_code=404, detail="Rango de lente no encontrado")

        if rangolente_update.rango is not None:
            dup_query = select(RangoLente).where(
                RangoLente.rango == rangolente_update.rango,
                RangoLente.id != rangolente_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otro rango de lente con ese valor")

        for key, value in rangolente_update.model_dump(exclude_unset=True).items():
            setattr(rangolente, key, value)

        db.add(rangolente)
        await db.commit()
        await db.refresh(rangolente)
        return rangolente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{rangolente_id}")
async def delete_rangolente(rangolente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(RangoLente).where(RangoLente.id == rangolente_id)
        result = await db.execute(query)
        rangolente = result.scalar_one_or_none()
        if not rangolente:
            raise HTTPException(status_code=404, detail="Rango de lente no encontrado")

        await db.delete(rangolente)
        await db.commit()
        return {"detail": "Rango de lente eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))