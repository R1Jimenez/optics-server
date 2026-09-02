from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.tipo_venta_model import TipoVenta, TipoVentaCreate, TipoVentaUpdate, TipoVentaOut

router = APIRouter(prefix = "/tipo_venta", tags=["Tipo de Venta"], dependencies=[Depends(get_current_user)])

@router.post('/create', response_model=TipoVentaOut)
async def create_tipo_venta(tipo_venta: TipoVentaCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoVenta).where(TipoVenta.venta == tipo_venta.venta)
        result = await db.execute(query)
        existing_tipo_venta = result.scalar_one_or_none()
        if existing_tipo_venta:
            raise HTTPException(status_code=400, detail="Este tipo de venta ya existe")
        
        new_tipo_venta = TipoVenta(venta=tipo_venta.venta)
        db.add(new_tipo_venta)
        await db.commit()
        await db.refresh(new_tipo_venta)
        return new_tipo_venta
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/all", response_model=list[TipoVentaOut])
async def get_all_tipo_venta(db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoVenta)
        result = await db.execute(query)
        tipo_ventas = result.scalars().all()
        return tipo_ventas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{tipo_venta_id}", response_model=TipoVentaOut)
async def get_tipo_venta(tipo_venta_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoVenta).where(TipoVenta.id == tipo_venta_id)
        result = await db.execute(query)
        tipo_venta = result.scalar_one_or_none()
        if not tipo_venta:
            raise HTTPException(status_code=404, detail="Tipo de venta no encontrado")
        return tipo_venta
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/update/{tipo_venta_id}", response_model=TipoVentaOut)
async def update_tipo_venta(tipo_venta_id: int, tipo_venta_update: TipoVentaUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoVenta).where(TipoVenta.id == tipo_venta_id)
        result = await db.execute(query)
        tipo_venta = result.scalar_one_or_none()
        if not tipo_venta:
            raise HTTPException(status_code=404, detail="Tipo de venta no encontrado")
        
        for key, value in tipo_venta_update.dict(exclude_unset=True).items():
            setattr(tipo_venta, key, value)
        
        db.add(tipo_venta)
        await db.commit()
        await db.refresh(tipo_venta)
        return tipo_venta
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/delete/{tipo_venta_id}")
async def delete_tipo_venta(tipo_venta_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(TipoVenta).where(TipoVenta.id == tipo_venta_id)
        result = await db.execute(query)
        tipo_venta = result.scalar_one_or_none()
        if not tipo_venta:
            raise HTTPException(status_code=404, detail="Tipo de venta no encontrado")
        
        await db.delete(tipo_venta)
        await db.commit()
        return {"detail": "Tipo de venta eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))