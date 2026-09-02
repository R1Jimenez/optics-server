from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.material_model import Material, MaterialCreate, MaterialUpdate, MaterialOut

router = APIRouter(prefix="/materiales", tags=["Materiales"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=MaterialOut)
async def create_material(material: MaterialCreate, db: AsyncSession = Depends(get_db)):
    
    try:
        existing_material = select(Material).where(Material.material == material.material)
        result = await db.execute(existing_material)
        existing_material_db = result.scalars().first()

        if existing_material_db:
            raise HTTPException(status_code=400, detail="Este material ya existe")

        new_material = Material(
            material = material.material
        )

        db.add(new_material)
        await db.commit()
        await db.refresh(new_material)
        return new_material
    
    except Exception as e:
        await db.rollback()
        print(f"Error al crear material: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[MaterialOut])
async def get_all_materiales(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Material)
        result = await db.execute(query)
        materiales = result.scalars().all()
        return materiales
    
    except Exception as e:
        print(f"Error al obtener materiales: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{material_id}", response_model=MaterialOut)
async def get_material(material_id: int, db: AsyncSession = Depends(get_db)):
    
    try:
        query = select(Material).where(Material.id == material_id)
        result = await db.execute(query)
        material = result.scalar_one_or_none()
        if not material:
            raise HTTPException(status_code=404, detail="Material no encontrado")
        return material
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener material: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{material_id}", response_model=MaterialOut)
async def update_material(material_id: int, material_update: MaterialUpdate, db: AsyncSession = Depends(get_db)):
    
    try:
        query = select(Material).where(Material.id == material_id)
        result = await db.execute(query)
        material = result.scalar_one_or_none()
        if not material:
            raise HTTPException(status_code=404, detail="Material no encontrado")

        material.material = material_update.material

        db.add(material)
        await db.commit()
        await db.refresh(material)
        return material
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar material: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{material_id}")
async def delete_material(material_id: int, db: AsyncSession = Depends(get_db)):
    
    try:
        query = select(Material).where(Material.id == material_id)
        result = await db.execute(query)
        material = result.scalar_one_or_none()
        if not material:
            raise HTTPException(status_code=404, detail="Material no encontrado")

        await db.delete(material)
        await db.commit()
        return {"detail": "Material eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar material: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )