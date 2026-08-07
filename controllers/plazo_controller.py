from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.plazo_model import Plazo, PlazoCreate, PlazoUpdate, PlazoOut

router = APIRouter(prefix="/plazos", tags=["Plazos"])

@router.post("/create", response_model=PlazoOut)
async def create_plazo(plazo: PlazoCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Plazo).where(Plazo.plazo == plazo.plazo)
        result = await db.execute(query)
        existing_plazo = result.scalar_one_or_none()
        if existing_plazo:
            raise HTTPException(status_code=400, detail="Este plazo ya existe")
        
        new_plazo = Plazo(plazo=plazo.plazo)
        db.add(new_plazo)
        await db.commit()
        await db.refresh(new_plazo)
        return new_plazo
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
    
@router.get("/{plazo_id}", response_model=PlazoOut)
async def get_plazo(plazo_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Plazo).where(Plazo.id == plazo_id)
        result = await db.execute(query)
        plazo = result.scalar_one_or_none()
        if not plazo:
            raise HTTPException(status_code=404, detail="Plazo no encontrado")
        return plazo
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
        
        for key, value in plazo_update.dict(exclude_unset=True).items():
            setattr(plazo, key, value)

        db.add(plazo)
        await db.commit()
        await db.refresh(plazo)
        return plazo
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