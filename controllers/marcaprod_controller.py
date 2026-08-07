from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.marcaprod_model import MarcaProd, MarcaProdCreate, MarcaProdUpdate, MarcaProdOut

router = APIRouter(prefix="/marcaprod", tags=["Marca de Producto"])

@router.post('/create', response_model=MarcaProdOut)
async def create_marcaprod(marcaprod: MarcaProdCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MarcaProd).where(MarcaProd.descripcion == marcaprod.descripcion)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Esta marca de producto ya existe")

        new_marcaprod = MarcaProd(descripcion=marcaprod.descripcion)
        db.add(new_marcaprod)
        await db.commit()
        await db.refresh(new_marcaprod)
        return new_marcaprod
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[MarcaProdOut])
async def get_all_marcaprod(db: AsyncSession = Depends(get_db)):
    try:
        query = select(MarcaProd)
        result = await db.execute(query)
        marcaprods = result.scalars().all()
        return marcaprods
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{marcaprod_id}", response_model=MarcaProdOut)
async def get_marcaprod(marcaprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MarcaProd).where(MarcaProd.id == marcaprod_id)
        result = await db.execute(query)
        marcaprod = result.scalar_one_or_none()
        if not marcaprod:
            raise HTTPException(status_code=404, detail="Marca de producto no encontrada")
        return marcaprod
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{marcaprod_id}", response_model=MarcaProdOut)
async def update_marcaprod(marcaprod_id: int, marcaprod_update: MarcaProdUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MarcaProd).where(MarcaProd.id == marcaprod_id)
        result = await db.execute(query)
        marcaprod = result.scalar_one_or_none()
        if not marcaprod:
            raise HTTPException(status_code=404, detail="Marca de producto no encontrada")

        if marcaprod_update.descripcion is not None:
            dup_query = select(MarcaProd).where(
                MarcaProd.descripcion == marcaprod_update.descripcion,
                MarcaProd.id != marcaprod_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otra marca de producto con esa descripción")

        for key, value in marcaprod_update.model_dump(exclude_unset=True).items():
            setattr(marcaprod, key, value)

        db.add(marcaprod)
        await db.commit()
        await db.refresh(marcaprod)
        return marcaprod
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{marcaprod_id}")
async def delete_marcaprod(marcaprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(MarcaProd).where(MarcaProd.id == marcaprod_id)
        result = await db.execute(query)
        marcaprod = result.scalar_one_or_none()
        if not marcaprod:
            raise HTTPException(status_code=404, detail="Marca de producto no encontrada")

        await db.delete(marcaprod)
        await db.commit()
        return {"detail": "Marca de producto eliminada exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))