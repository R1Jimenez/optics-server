from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from database.database import get_db
from middleware.auth import get_current_user
from models.clientes_model import Cliente, CreateCliente, ClienteOut, ClienteUpdate
from models.tipo_cliente_model import Tipo_Cliente

router = APIRouter(prefix="/cliente", tags=["cliente"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=ClienteOut)
async def create_cliente(cliente: CreateCliente, db: AsyncSession = Depends(get_db)):

    try:
        existing_cliente = select(Cliente).where(Cliente.email == cliente.email)
        result = await db.execute(existing_cliente)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="El cliente con este correo ya se encuentra registrado"
            )
        
        existing_rfc = select(Cliente).where(Cliente.rfc == cliente.rfc)
        result_rfc = await db.execute(existing_rfc)

        if result_rfc.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="El cliente con este RFC ya se encuentra registrado"
            )
        
        # Validar que el tipo de cliente existe
        query = select(Tipo_Cliente).where(Tipo_Cliente.id == cliente.tipocliente)
        result_tipo = await db.execute(query)
        tipo_exists = result_tipo.scalar_one_or_none()

        if not tipo_exists:
            raise HTTPException(
                status_code=400,
                detail=f"El tipo de cliente con ID {cliente.tipocliente} no existe"
            )
        
        new_cliente = Cliente(
            nombres = cliente.nombres,
            apellidos = cliente.apellidos,
            rfc = cliente.rfc,
            calle = cliente.calle,
            numero = cliente.numero,
            colonia = cliente.colonia,
            ciudad = cliente.ciudad,
            estado = cliente.estado,
            codigopostal = cliente.codigopostal,
            telefono = cliente.telefono,
            email = cliente.email,
            contacto = cliente.contacto,
            tipocliente = cliente.tipocliente
        )

        db.add(new_cliente)
        await db.commit()
        await db.refresh(new_cliente)
        return new_cliente
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@router.get("/all", response_model=list[ClienteOut])
async def get_all_clientes(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Cliente)
        result = await db.execute(query)
        clientes = result.scalars().all()
        return clientes
    
    except Exception as e:
        print(f"Error al obtener clientes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@router.get("/search")
async def search_clientes(cliente: str, db: AsyncSession = Depends(get_db)):
    query = select(Cliente).where(
        or_(
            Cliente.nombres.ilike(f"%{cliente}%"),
            Cliente.apellidos.ilike(f"%{cliente}%")
        )
    ).limit(10)  # Limitar resultados
    result = await db.execute(query)
    return result.scalars().all()
    
@router.get("/{cliente_id}", response_model=ClienteOut)
async def get_cliente(cliente_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Cliente).where(Cliente.id == cliente_id)
        result = await db.execute(query)
        cliente = result.scalar_one_or_none()

        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado o inexistente"
            )
        
        return cliente
    except Exception as e:
        print(f"Error al obtener cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{cliente_id}", response_model=ClienteOut)
async def update_cliente(cliente_id: int, cliente_update: ClienteUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Cliente).where(Cliente.id == cliente_id)
        result = await db.execute(query)
        cliente = result.scalar_one_or_none()

        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado o inexistente"
            )
        
        # Validar email solo si se proporciona y excluir el cliente actual
        if cliente_update.email is not None:
            existing_cliente = select(Cliente).where(
                Cliente.email == cliente_update.email,
                Cliente.id != cliente_id
            )
            result = await db.execute(existing_cliente)

            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="El cliente con este correo ya se encuentra registrado"
                )
        
        # Validar RFC solo si se proporciona y excluir el cliente actual
        if cliente_update.rfc is not None:
            existing_rfc = select(Cliente).where(
                Cliente.rfc == cliente_update.rfc,
                Cliente.id != cliente_id
            )
            result_rfc = await db.execute(existing_rfc)

            if result_rfc.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="El cliente con este RFC ya se encuentra registrado"
                )
        
        # Validar tipo de cliente si se proporciona
        if cliente_update.tipocliente is not None:
            query = select(Tipo_Cliente).where(Tipo_Cliente.id == cliente_update.tipocliente)
            result_tipo = await db.execute(query)
            tipo_exists = result_tipo.scalar_one_or_none()

            if not tipo_exists:
                raise HTTPException(
                    status_code=400,
                    detail=f"El tipo de cliente con ID {cliente_update.tipocliente} no existe"
                )

        # Actualizar solo los campos proporcionados
        update_data = cliente_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se proporcionaron datos para actualizar"
            )

        for key, value in update_data.items():
            setattr(cliente, key, value)

        db.add(cliente)
        await db.commit()
        await db.refresh(cliente)
        return cliente
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{cliente_id}")
async def delete_cliente(cliente_id: int, db: AsyncSession = Depends(get_db)):
    
    try:
        query = select(Cliente).where(Cliente.id == cliente_id)
        result = await db.execute(query)
        cliente = result.scalar_one_or_none()

        if not cliente:
            raise HTTPException(
                status_code=404,
                detail="Cliente no encontrado o inexistente"
            )
        
        await db.delete(cliente)
        await db.commit()

        return {"message": "Cliente eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )