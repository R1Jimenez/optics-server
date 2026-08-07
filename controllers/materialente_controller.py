from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.materialente_model import MateriaLente, MateriaLenteCreate, MateriaLenteUpdate, MateriaLenteOut

router = APIRouter(prefix="/materialente", tags=["Materia de Lente"])


@router.post('/create', response_model=MateriaLenteOut)
async def create_materialente(materalente: MateriaLenteCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MateriaLente).where(MateriaLente.descripcion == materalente.descripcion)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Esta materia de lente ya existe")

        new_materalente = MateriaLente(descripcion=materalente.descripcion)
        db.add(new_materalente)
        await db.commit()
        await db.refresh(new_materalente)
        return new_materalente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[MateriaLenteOut])
async def get_all_materalente(db: AsyncSession = Depends(get_db)):
    try:
        query = select(MateriaLente)
        result = await db.execute(query)
        materalentes = result.scalars().all()
        return materalentes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{materalente_id}", response_model=MateriaLenteOut)
async def get_materalente(materalente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MateriaLente).where(MateriaLente.id == materalente_id)
        result = await db.execute(query)
        materalente = result.scalar_one_or_none()
        if not materalente:
            raise HTTPException(status_code=404, detail="Materia de lente no encontrada")
        return materalente
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{materalente_id}", response_model=MateriaLenteOut)
async def update_materalente(materalente_id: int, materalente_update: MateriaLenteUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MateriaLente).where(MateriaLente.id == materalente_id)
        result = await db.execute(query)
        materalente = result.scalar_one_or_none()
        if not materalente:
            raise HTTPException(status_code=404, detail="Materia de lente no encontrada")

        if materalente_update.descripcion is not None:
            dup_query = select(MateriaLente).where(
                MateriaLente.descripcion == materalente_update.descripcion,
                MateriaLente.id != materalente_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otra materia de lente con esa descripción")

        for key, value in materalente_update.model_dump(exclude_unset=True).items():
            setattr(materalente, key, value)

        db.add(materalente)
        await db.commit()
        await db.refresh(materalente)
        return materalente
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{materalente_id}")
async def delete_materalente(materalente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MateriaLente).where(MateriaLente.id == materalente_id)
        result = await db.execute(query)
        materalente = result.scalar_one_or_none()
        if not materalente:
            raise HTTPException(status_code=404, detail="Materia de lente no encontrada")

        await db.delete(materalente)
        await db.commit()
        return {"detail": "Materia de lente eliminada exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))