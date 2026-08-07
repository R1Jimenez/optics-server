from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.ordenproducto_model import OrdenProducto, OrdenProductoCreate, OrdenProductoUpdate, OrdenProductoOut

router = APIRouter(prefix="/ordenproducto", tags=["Orden de Producto"])


@router.post('/create', response_model=OrdenProductoOut)
async def create_ordenproducto(ordenproducto: OrdenProductoCreate, db: AsyncSession = Depends(get_db)):
    try:
        new_ordenproducto = OrdenProducto(
            id_tipo_prod=ordenproducto.id_tipo_prod,
            id_marca_prod=ordenproducto.id_marca_prod,
            id_modelo_prod=ordenproducto.id_modelo_prod,
            id_tipo_lente=ordenproducto.id_tipo_lente,
            id_materia_lente=ordenproducto.id_materia_lente,
            id_color_lente=ordenproducto.id_color_lente,
            id_rango_lente=ordenproducto.id_rango_lente,
        )
        db.add(new_ordenproducto)
        await db.commit()
        await db.refresh(new_ordenproducto)
        return new_ordenproducto
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all", response_model=list[OrdenProductoOut])
async def get_all_ordenproducto(db: AsyncSession = Depends(get_db)):
    try:
        query = select(OrdenProducto)
        result = await db.execute(query)
        ordenproductos = result.scalars().all()
        return ordenproductos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ordenproducto_id}", response_model=OrdenProductoOut)
async def get_ordenproducto(ordenproducto_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(OrdenProducto).where(OrdenProducto.id == ordenproducto_id)
        result = await db.execute(query)
        ordenproducto = result.scalar_one_or_none()
        if not ordenproducto:
            raise HTTPException(status_code=404, detail="Orden de producto no encontrada")
        return ordenproducto
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update/{ordenproducto_id}", response_model=OrdenProductoOut)
async def update_ordenproducto(ordenproducto_id: int, ordenproducto_update: OrdenProductoUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(OrdenProducto).where(OrdenProducto.id == ordenproducto_id)
        result = await db.execute(query)
        ordenproducto = result.scalar_one_or_none()
        if not ordenproducto:
            raise HTTPException(status_code=404, detail="Orden de producto no encontrada")

        for key, value in ordenproducto_update.model_dump(exclude_unset=True).items():
            setattr(ordenproducto, key, value)

        db.add(ordenproducto)
        await db.commit()
        await db.refresh(ordenproducto)
        return ordenproducto
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{ordenproducto_id}")
async def delete_ordenproducto(ordenproducto_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(OrdenProducto).where(OrdenProducto.id == ordenproducto_id)
        result = await db.execute(query)
        ordenproducto = result.scalar_one_or_none()
        if not ordenproducto:
            raise HTTPException(status_code=404, detail="Orden de producto no encontrada")

        await db.delete(ordenproducto)
        await db.commit()
        return {"detail": "Orden de producto eliminada exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))