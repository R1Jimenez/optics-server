from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from passlib.context import CryptContext
from models.users_model import User, UserSignUp, UserLogin, UserUpdate, UserOut, Token
from sqlalchemy import any_
from models.sucursales_model import Sucursal
from models.user_roles_model import UserRole
from middleware.auth import create_access_token, get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    password = password[:72]  # bcrypt tiene límite de 72 bytes
    return pwd_context.hash(password)

async def build_users_out(users: list[User], db: AsyncSession) -> list[UserOut]:
    sucursal_ids = set()
    for u in users:
        sucursal_ids.add(int(u.Sucursal))
        sucursal_ids.update(int(sid) for sid in (u.sucursal_acces or []))

    sucursales_query = select(Sucursal).where(Sucursal.id.in_(sucursal_ids))
    sucursales_result = await db.execute(sucursales_query)
    sucursales_map = {s.id: s.sucursal for s in sucursales_result.scalars().all()}

    return [
        UserOut(
            id=u.id,
            nombres=u.nombres,
            apellidos=u.apellidos,
            usuario=u.usuario,
            email=u.email,
            telefono=u.telefono,
            Sucursal=sucursales_map.get(int(u.Sucursal), ""),
            sucursal_acces=[sucursales_map[int(sid)] for sid in u.sucursal_acces if int(sid) in sucursales_map],
            roles=u.roles
        )
        for u in users
    ]

async def build_user_out(user: User, db: AsyncSession) -> UserOut:
    return (await build_users_out([user], db))[0]

@router.post("/signup", response_model=UserOut)
async def user_signup(user: UserSignUp, db: AsyncSession = Depends(get_db)):

    try:
        # Verificar si el usuario ya existe
        existing_user = select(User).where(User.usuario == user.usuario)
        result = await db.execute(existing_user)
        user_exists = result.scalar_one_or_none()

        if user_exists:
            raise HTTPException(
                status_code=400,
                detail="El usuario ya está en uso"
            )
        
        existing_email = select(User).where(User.email == user.email)
        email_result = await db.execute(existing_email)
        email_exists = email_result.scalar_one_or_none()

        if email_exists:
            raise HTTPException(
                status_code=400,
                detail="El correo electrónico ya está en uso"
            )

        if not user.roles or len(user.roles) == 0:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar al menos un rol de usuario"
            )
        
        for role_id in user.roles:
            role_query = select(UserRole).where(UserRole.id == role_id)
            role_result = await db.execute(role_query)
            role_exists = role_result.scalar_one_or_none()
            
            if not role_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"El rol con ID {role_id} no existe"
                )
        
        sucursalquery = select(Sucursal).where(user.Sucursal == Sucursal.id)
        sucursal = await db.execute(sucursalquery)
        sucursalvalid = sucursal.scalar_one_or_none()

        if not sucursalvalid:
            raise HTTPException(
                status_code=400,
                detail = "La sucursal seleccionada no existe"
            )
        
        if not user.sucursal_acces or len(user.sucursal_acces) == 0:
            raise HTTPException (
                status_code = 400,
                detail = "Debe proporcionar al menos una sucursal de acceso"
            )
        
        for suc in user.sucursal_acces:
            sucursal_query = select(Sucursal).where(Sucursal.id == suc)
            sucursal_result = await db.execute(sucursal_query)
            sucursal_exists = sucursal_result.scalar_one_or_none()
            
            if not sucursal_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"Una de las sucursales de acceso seleccionada no existe"
                )
        
        new_user = User (
            nombres = user.nombres,
            apellidos = user.apellidos,
            usuario = user.usuario,
            email = user.email,
            telefono = user.telefono,
            Sucursal = user.Sucursal,
            sucursal_acces = user.sucursal_acces,
            roles = user.roles,
            hashed_password = hash_password(user.password)
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return await build_user_out(new_user, db)
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@router.post("/login", response_model=Token)
async def user_login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    try:
        query = select(User).where(User.usuario == credentials.usuario)
        result = await db.execute(query)
        user_result = result.scalar_one_or_none()

        if not user_result or not pwd_context.verify(credentials.password, user_result.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Usuario o contraseña incorrectos"
            )

        access_token = create_access_token(
            data={
                "sub": user_result.usuario,
                "id": user_result.id,
                "roles": user_result.roles,
                "sucursal_acces": user_result.sucursal_acces,
            }
        )

        user_out = await build_user_out(user_result, db)
        return Token(access_token=access_token, user=user_out)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al iniciar sesión: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[UserOut], dependencies=[Depends(get_current_user)])
async def get_all_users(
    usuario: str | None = None,
    sucursal_id: int | None = None,
    rol_id: int | None = None,
    activos: bool | None = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(User)
        
        # Aplicar filtros opcionales
        if usuario:
            query = query.where(
                (User.usuario.ilike(f"%{usuario}%")) | 
                (User.nombres.ilike(f"%{usuario}%")) |
                (User.apellidos.ilike(f"%{usuario}%"))
            )
        
        if sucursal_id:
            # Filtrar usuarios que tengan acceso a esta sucursal
            query = query.where(sucursal_id == any_(User.sucursal_acces))
        
        if rol_id:
            # Filtrar usuarios que tengan este rol
            query = query.where(rol_id == any_(User.roles))
        
        # Para filtrar activos necesitarías un campo is_active en el modelo
        # o hacer join con user_roles para verificar si tienen roles activos
        
        result = await db.execute(query)
        users = result.scalars().all()
        return await build_users_out(users, db)
    
    except Exception as e:
        print(f"Error al obtener usuarios: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_user)])
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user_result = result.scalar_one_or_none()

        if not user_result:
            raise HTTPException(
                status_code = 404,
                detail = "Usuario no encontrado o inexistente"
            )
        
        return await build_user_out(user_result, db)
    
    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{user_id}", response_model=UserOut, dependencies=[Depends(get_current_user)])
async def update_user(user_id: int, user_update: UserUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(User).where(User.id == user_id)
        result = await db.execute(query)
        user_result = result.scalar_one_or_none()

        if not user_result:
            raise HTTPException(
                status_code = 404,
                detail = "Usuario no encontrado o inexistente"
            )
        
        update_data = user_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se proporcionaron datos para actualizar"
            )
        
        existing_user_query = select(User).where(User.usuario == update_data.get("usuario"), User.id != user_id)
        existing_user_result = await db.execute(existing_user_query)
        existing_user = existing_user_result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Este nombre de usuario ya está en uso"
            )
        
        existing_email_query = select(User).where(User.email == update_data.get("email"), User.id != user_id)
        existing_email_result = await db.execute(existing_email_query)
        existing_email_user = existing_email_result.scalar_one_or_none()

        if existing_email_user:
            raise HTTPException(
                status_code=400,
                detail="Este correo electrónico ya está en uso"
            )

        for key, value in update_data.items():
            if key == "password":
                setattr(user_result, "hashed_password", hash_password(value))
            else:
                setattr(user_result, key, value)

        db.add(user_result)
        await db.commit()
        await db.refresh(user_result)
        return await build_user_out(user_result, db)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{user_id}", dependencies=[Depends(get_current_user)])
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):

    try:
        queey = select(User).where(User.id == user_id)
        result = await db.execute(queey)
        user_result = result.scalar_one_or_none()

        if not user_result:
            raise HTTPException(
                status_code = 404,
                detail = "Usuario no encontrado o inexistente"
            )
        
        await db.delete(user_result)
        await db.commit()
        return {"detail": "Usuario eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar usuario: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )