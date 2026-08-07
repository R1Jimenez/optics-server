from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.tiprod_model import TipProd, TipProdCreate, TiProdUpdate, TiProdOut

router = APIRouter(prefix="/tipoprod", tags=["Tipo de Producto"])

@router.post('/create', response_model=TiProdOut)
async def create_tipprod(tipprod: TipProdCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipProd).where(TipProd.descripcion == tipprod.descripcion)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Este tipo de producto ya existe")

        new_tipprod = TipProd(descripcion=tipprod.descripcion)
        db.add(new_tipprod)
        await db.commit()
        await db.refresh(new_tipprod)
        return new_tipprod
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[TiProdOut])
async def get_all_tipprod(db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipProd)
        result = await db.execute(query)
        tipprods = result.scalars().all()
        return tipprods
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tipprod_id}", response_model=TiProdOut)
async def get_tipprod(tipprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipProd).where(TipProd.id == tipprod_id)
        result = await db.execute(query)
        tipprod = result.scalar_one_or_none()
        if not tipprod:
            raise HTTPException(status_code=404, detail="Tipo de producto no encontrado")
        return tipprod
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{tipprod_id}", response_model=TiProdOut)
async def update_tipprod(tipprod_id: int, tipprod_update: TiProdUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipProd).where(TipProd.id == tipprod_id)
        result = await db.execute(query)
        tipprod = result.scalar_one_or_none()
        if not tipprod:
            raise HTTPException(status_code=404, detail="Tipo de producto no encontrado")

        # Verificar duplicado si se está cambiando la descripción
        if tipprod_update.descripcion is not None:
            dup_query = select(TipProd).where(
                TipProd.descripcion == tipprod_update.descripcion,
                TipProd.id != tipprod_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otro tipo de producto con esa descripción")

        for key, value in tipprod_update.model_dump(exclude_unset=True).items():
            setattr(tipprod, key, value)

        db.add(tipprod)
        await db.commit()
        await db.refresh(tipprod)
        return tipprod
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{tipprod_id}")
async def delete_tipprod(tipprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipProd).where(TipProd.id == tipprod_id)
        result = await db.execute(query)
        tipprod = result.scalar_one_or_none()
        if not tipprod:
            raise HTTPException(status_code=404, detail="Tipo de producto no encontrado")

        await db.delete(tipprod)
        await db.commit()
        return {"detail": "Tipo de producto eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))