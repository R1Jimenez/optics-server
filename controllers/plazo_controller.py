from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.plazo_model import Plazo, PlazoCreate, PlazoUpdate, PlazoOut
from models.tipo_venta_model import TipoVenta

router = APIRouter(prefix="/plazos", tags=["Plazos"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=PlazoOut)
async def create_plazo(plazo: PlazoCreate, db: AsyncSession = Depends(get_db)):
    try:
        tipo_venta_query = select(TipoVenta).where(TipoVenta.id == plazo.tipo_venta_id)
        tipo_venta_result = await db.execute(tipo_venta_query)
        tipo_venta = tipo_venta_result.scalar_one_or_none()
        if not tipo_venta:
            raise HTTPException(status_code=404, detail=f"El tipo de venta con ID {plazo.tipo_venta_id} no existe")

        query = select(Plazo).where(
            Plazo.plazo == plazo.plazo,
            Plazo.tipo_venta_id == plazo.tipo_venta_id
        )
        result = await db.execute(query)
        existing_plazo = result.scalar_one_or_none()
        if existing_plazo:
            raise HTTPException(status_code=400, detail="Este plazo ya existe")
        
        new_plazo = Plazo(plazo=plazo.plazo, tipo_venta_id=plazo.tipo_venta_id)
        db.add(new_plazo)
        await db.commit()
        await db.refresh(new_plazo)
        return new_plazo
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/all", response_model=list[PlazoOut])
async def get_all_plazos(db: AsyncSession = Depends(get_db)):
    try:
        query = select(Plazo)
        result = await db.execute(query)
        plazos = result.scalars().all()
        return plazos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{tipo_venta_id}", response_model=list[PlazoOut])
async def get_plazo(tipo_venta_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Plazo).where(Plazo.tipo_venta_id == tipo_venta_id)
        result = await db.execute(query)
        plazos = result.scalars().all()
        if not plazos:
            raise HTTPException(status_code=404, detail="Plazos no encontrados")
        return plazos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/update/{plazo_id}", response_model=PlazoOut)
async def update_plazo(plazo_id: int, plazo_update: PlazoUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Plazo).where(Plazo.id == plazo_id)
        result = await db.execute(query)
        plazo = result.scalar_one_or_none()
        if not plazo:
            raise HTTPException(status_code=404, detail="Plazo no encontrado")

        update_data = plazo_update.dict(exclude_unset=True)

        if "tipo_venta_id" in update_data:
            tipo_venta_query = select(TipoVenta).where(TipoVenta.id == update_data["tipo_venta_id"])
            tipo_venta_result = await db.execute(tipo_venta_query)
            tipo_venta = tipo_venta_result.scalar_one_or_none()
            if not tipo_venta:
                raise HTTPException(status_code=404, detail=f"El tipo de venta con ID {update_data['tipo_venta_id']} no existe")

        for key, value in update_data.items():
            setattr(plazo, key, value)

        db.add(plazo)
        await db.commit()
        await db.refresh(plazo)
        return plazo
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/delete/{plazo_id}")
async def delete_plazo(plazo_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Plazo).where(Plazo.id == plazo_id)
        result = await db.execute(query)
        plazo = result.scalar_one_or_none()
        if not plazo:
            raise HTTPException(status_code=404, detail="Plazo no encontrado")
        
        await db.delete(plazo)
        await db.commit()
        return {"detail": "Plazo eliminado exitosamente"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))