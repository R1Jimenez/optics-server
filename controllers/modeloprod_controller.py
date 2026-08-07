from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.modeloprod_model import ModeloProd, ModeloProdCreate, ModeloProdUpdate, ModeloProdOut

router = APIRouter(prefix="/modeloprod", tags=["Modelo de Producto"])


@router.post('/create', response_model=ModeloProdOut)
async def create_modeloprod(modeloprod: ModeloProdCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ModeloProd).where(ModeloProd.descripcion == modeloprod.descripcion)
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Este modelo de producto ya existe")

        new_modeloprod = ModeloProd(descripcion=modeloprod.descripcion)
        db.add(new_modeloprod)
        await db.commit()
        await db.refresh(new_modeloprod)
        return new_modeloprod
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[ModeloProdOut])
async def get_all_modeloprod(db: AsyncSession = Depends(get_db)):
    try:
        query = select(ModeloProd)
        result = await db.execute(query)
        modeloprods = result.scalars().all()
        return modeloprods
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{modeloprod_id}", response_model=ModeloProdOut)
async def get_modeloprod(modeloprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ModeloProd).where(ModeloProd.id == modeloprod_id)
        result = await db.execute(query)
        modeloprod = result.scalar_one_or_none()
        if not modeloprod:
            raise HTTPException(status_code=404, detail="Modelo de producto no encontrado")
        return modeloprod
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{modeloprod_id}", response_model=ModeloProdOut)
async def update_modeloprod(modeloprod_id: int, modeloprod_update: ModeloProdUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ModeloProd).where(ModeloProd.id == modeloprod_id)
        result = await db.execute(query)
        modeloprod = result.scalar_one_or_none()
        if not modeloprod:
            raise HTTPException(status_code=404, detail="Modelo de producto no encontrado")

        if modeloprod_update.descripcion is not None:
            dup_query = select(ModeloProd).where(
                ModeloProd.descripcion == modeloprod_update.descripcion,
                ModeloProd.id != modeloprod_id
            )
            dup_result = await db.execute(dup_query)
            if dup_result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Ya existe otro modelo de producto con esa descripción")

        for key, value in modeloprod_update.model_dump(exclude_unset=True).items():
            setattr(modeloprod, key, value)

        db.add(modeloprod)
        await db.commit()
        await db.refresh(modeloprod)
        return modeloprod
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{modeloprod_id}")
async def delete_modeloprod(modeloprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(ModeloProd).where(ModeloProd.id == modeloprod_id)
        result = await db.execute(query)
        modeloprod = result.scalar_one_or_none()
        if not modeloprod:
            raise HTTPException(status_code=404, detail="Modelo de producto no encontrado")

        await db.delete(modeloprod)
        await db.commit()
        return {"detail": "Modelo de producto eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))