from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.tipolente_model import TipoLente, TipoLenteCreate, TipoLenteUpdate, TipoLenteOut

router = APIRouter(prefix="/tipolente", tags=["Tipo de Lente"], dependencies=[Depends(get_current_user)])


@router.post('/create', response_model=TipoLenteOut)
async def create_tipolente(tipolente: TipoLenteCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoLente).where(TipoLente.descripcion == tipolente.descripcion)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Este tipo de lente ya existe")

        new_tipolente = TipoLente(descripcion=tipolente.descripcion)
        db.add(new_tipolente)
        await db.commit()
        await db.refresh(new_tipolente)
        return new_tipolente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[TipoLenteOut])
async def get_all_tipolente(db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoLente)
        result = await db.execute(query)
        tipolentes = result.scalars().all()
        return tipolentes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tipolente_id}", response_model=TipoLenteOut)
async def get_tipolente(tipolente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoLente).where(TipoLente.id == tipolente_id)
        result = await db.execute(query)
        tipolente = result.scalar_one_or_none()
        if not tipolente:
            raise HTTPException(status_code=404, detail="Tipo de lente no encontrado")
        return tipolente
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{tipolente_id}", response_model=TipoLenteOut)
async def update_tipolente(tipolente_id: int, tipolente_update: TipoLenteUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoLente).where(TipoLente.id == tipolente_id)
        result = await db.execute(query)
        tipolente = result.scalar_one_or_none()
        if not tipolente:
            raise HTTPException(status_code=404, detail="Tipo de lente no encontrado")

        if tipolente_update.descripcion is not None:
            dup_query = select(TipoLente).where(
                TipoLente.descripcion == tipolente_update.descripcion,
                TipoLente.id != tipolente_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otro tipo de lente con esa descripción")

        for key, value in tipolente_update.model_dump(exclude_unset=True).items():
            setattr(tipolente, key, value)

        db.add(tipolente)
        await db.commit()
        await db.refresh(tipolente)
        return tipolente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{tipolente_id}")
async def delete_tipolente(tipolente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoLente).where(TipoLente.id == tipolente_id)
        result = await db.execute(query)
        tipolente = result.scalar_one_or_none()
        if not tipolente:
            raise HTTPException(status_code=404, detail="Tipo de lente no encontrado")

        await db.delete(tipolente)
        await db.commit()
        return {"detail": "Tipo de lente eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))