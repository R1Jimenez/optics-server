from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.user_roles_model import UserRole, UserRoleCreate, UserRoleOut

router = APIRouter(prefix="/users_roles", tags=["Users_Roles"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=UserRoleOut)
async def create_user_role(user_role: UserRoleCreate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(UserRole).where(UserRole.rol == user_role.rol)
        result = await db.execute(query)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="El rol de usuario ya existe"
            )
        
        new_role = UserRole(
            rol = user_role.rol,
            is_active = user_role.is_active
        )

        db.add(new_role)
        await db.commit()
        await db.refresh(new_role)
        return new_role
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear rol de usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[UserRoleOut])
async def get_all_user_roles(db: AsyncSession = Depends(get_db)):

    try:
        query = select(UserRole)
        result = await db.execute(query)
        roles = result.scalars().all()
        return roles
    
    except Exception as e:
        print(f"Error al obtener roles de usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{role_id}", response_model=UserRoleOut)
async def get_user_role(role_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(UserRole).where(UserRole.id == role_id)
        result = await db.execute(query)
        role = result.scalar_one_or_none()
        
        if not role:
            raise HTTPException(
                status_code=404,
                detail="Rol de usuario no encontrado"
            )

        return role
    
    except Exception as e:
        print(f"Error al obtener rol de usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{role_id}", response_model=UserRoleOut)
async def update_user_role(role_id: int, role_update: UserRoleCreate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(UserRole).where(UserRole.id == role_id)
        result = await db.execute(query)
        existing_role = result.scalar_one_or_none()

        if not existing_role:
            raise HTTPException(
                status_code=404,
                detail="Rol de usuario no encontrado"
            )
        
        update_data = role_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException (
                status_code = 400,
                detail = "No se han proporcionado datos por actualizar"
            )
        
        if "rol" in update_data:
            rol_query = select(UserRole).where(
                UserRole.rol == update_data["rol"],
                UserRole.id != role_id
            )
            rol_result = await db.execute(rol_query)
            rol_exists = rol_result.scalar_one_or_none()

            if rol_exists:
                raise HTTPException(
                    status_code=400,
                    detail="Este rol de usuario ya existe"
                )
            
        for key, value in update_data.items():
            setattr(existing_role, key, value)

        await db.commit()
        await db.refresh(existing_role)
        return existing_role
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar rol de usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{role_id}")
async def delete_user_role(role_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(UserRole).where(UserRole.id == role_id)
        result = await db.execute(query)
        existing_role = result.scalar_one_or_none()

        if not existing_role:
            raise HTTPException (
                status_code=404,
                detail="Rol de usuario no encontrado"
            )
        
        await db.delete(existing_role)
        await db.commit()
        return {"detail": "Rol de usuario eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar rol de usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
