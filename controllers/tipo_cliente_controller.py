from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.database import get_db
from middleware.auth import get_current_user
from models.tipo_cliente_model import Tipo_Cliente, TipoClienteCreate, TipoClienteUpdate, TipoClienteOut
from models.clientes_model import Cliente
from models.promociones_model import Promociones, PromocionCondicion

router = APIRouter(prefix="/tipo_cliente", tags=["Tipo_Cliente"], dependencies=[Depends(get_current_user)])


async def _validar_nombre_unico(db: AsyncSession, nombre: str, excluir_id: int | None = None) -> None:
    query = select(Tipo_Cliente.id).where(func.lower(Tipo_Cliente.cliente) == nombre.lower())
    if excluir_id is not None:
        query = query.where(Tipo_Cliente.id != excluir_id)
    if (await db.execute(query)).first():
        raise HTTPException(status_code=400, detail="Este tipo de cliente ya existe")


@router.post("/create", response_model=TipoClienteOut)
async def create_tipo_cliente(tipo_cliente: TipoClienteCreate, db: AsyncSession = Depends(get_db)):

    try:
        await _validar_nombre_unico(db, tipo_cliente.cliente)
        
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
        clientes = (
            select(Cliente.tipocliente, func.count(Cliente.id).label("total"))
            .group_by(Cliente.tipocliente)
            .subquery()
        )
        query = (
            select(Tipo_Cliente, func.coalesce(clientes.c.total, 0))
            .outerjoin(clientes, clientes.c.tipocliente == Tipo_Cliente.id)
            .order_by(func.lower(Tipo_Cliente.cliente))
        )
        result = await db.execute(query)
        return [
            TipoClienteOut(id=t.id, cliente=t.cliente, porcentaje_descuento=t.porcentaje_descuento, clientes=total)
            for t, total in result.all()
        ]
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
    except HTTPException:
        raise
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
        
        if tipo_cliente_update.cliente is not None:
            await _validar_nombre_unico(db, tipo_cliente_update.cliente, tipo_cliente_id)

        datos_actualizados = tipo_cliente_update.model_dump(exclude_unset=True, exclude_none=True)
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

        # borrarlo dejaria clientes sin descuento y promociones abiertas a todos los tipos
        clientes = await db.scalar(select(func.count(Cliente.id)).where(Cliente.tipocliente == tipo_cliente_id))
        promociones = await db.scalar(
            select(func.count(func.distinct(PromocionCondicion.promocion_id)))
            .join(Promociones, Promociones.id == PromocionCondicion.promocion_id)
            .where(
                PromocionCondicion.categoria == "tipos_cliente",
                PromocionCondicion.referencia_id == tipo_cliente_id,
                Promociones.activo.is_(True),
            )
        )
        en_uso = []
        if clientes:
            en_uso.append(f"{clientes} cliente(s)")
        if promociones:
            en_uso.append(f"{promociones} promoción(es) activa(s)")
        if en_uso:
            raise HTTPException(
                status_code=400,
                detail=f"No se puede eliminar: está asignado a {' y '.join(en_uso)}"
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