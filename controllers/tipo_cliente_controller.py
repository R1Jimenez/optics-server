from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.tipo_cliente_model import Tipo_Cliente, TipoClienteCreate, TipoClienteUpdate, TipoClienteOut

router = APIRouter(prefix="/tipo_cliente", tags=["Tipo_Cliente"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=TipoClienteOut)
async def create_tipo_cliente(tipo_cliente: TipoClienteCreate, db: AsyncSession = Depends(get_db)):

    try:
        existing_tipo = select(Tipo_Cliente).where(Tipo_Cliente.cliente == tipo_cliente.cliente)
        result = await db.execute(existing_tipo)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Este tipo de cliente ya existe"
            )
        
        new_tipo_cliente = Tipo_Cliente(
            cliente = tipo_cliente.cliente,
            porcentaje_descuento = tipo_cliente.porcentaje_descuento
        )

        db.add(new_tipo_cliente)
        await db.commit()
        await db.refresh(new_tipo_cliente)
        return new_tipo_cliente
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear tipo de cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[TipoClienteOut])
async def get_all_tipo_clientes(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Tipo_Cliente)
        result = await db.execute(query)

        tipos_clientes = result.scalars().all()
        return tipos_clientes
    except Exception as e:
        print(f"Error al obtener tipos de clientes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/{tipo_cliente_id}", response_model=TipoClienteOut)
async def get_tipo_cliente(tipo_cliente_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Tipo_Cliente).where(Tipo_Cliente.id == tipo_cliente_id)
        result = await db.execute(query)
        tipo_cliente = result.scalar_one_or_none()

        if not tipo_cliente:
            raise HTTPException(
                status_code=404,
                detail="Tipo de cliente no encontrado o inexistente"
            )
        
        return tipo_cliente
    except Exception as e:
        print(f"Error al obtener tipo de cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.post("/update/{tipo_cliente_id}", response_model=TipoClienteOut)
async def update_tipo_cliente(tipo_cliente_id: int, tipo_cliente_update: TipoClienteUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Tipo_Cliente).where(Tipo_Cliente.id == tipo_cliente_id)
        result = await db.execute(query)
        tipo_cliente = result.scalar_one_or_none()

        if not tipo_cliente:
            raise HTTPException(
                status_code=404,
                detail="Tipo de cliente no encontrado o inexistente"
            )
        
        nuevo_cliente = tipo_cliente_update.cliente if tipo_cliente_update.cliente is not None else tipo_cliente.cliente

        if not nuevo_cliente:
            raise HTTPException(
                status_code=400,
                detail="El campo 'cliente' no puede estar vacío"
            )
        
        # Validar que no exista otro registro con el mismo nombre (excluyendo el actual)
        existing_tipo = select(Tipo_Cliente).where(
            Tipo_Cliente.cliente == nuevo_cliente,
            Tipo_Cliente.id != tipo_cliente_id
        )
        result = await db.execute(existing_tipo)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Este tipo de cliente ya existe"
            )

        datos_actualizados = tipo_cliente_update.model_dump(exclude_unset=True)
        for campo, valor in datos_actualizados.items():
            setattr(tipo_cliente, campo, valor)

        db.add(tipo_cliente)
        await db.commit()
        await db.refresh(tipo_cliente)
        return tipo_cliente
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar tipo de cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{tipo_cliente_id}")
async def delete_tipo_cliente(tipo_cliente_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Tipo_Cliente).where(Tipo_Cliente.id == tipo_cliente_id)
        result = await db.execute(query)
        tipo_cliente = result.scalar_one_or_none()

        if not tipo_cliente:
            raise HTTPException(
                status_code=404,
                detail="Tipo de cliente no encontrado o inexistente"
            )
        
        await db.delete(tipo_cliente)
        await db.commit()
        return {"detail": "Tipo de cliente eliminado exitosamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar tipo de cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )