from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.ordenes_trabajo_model import (
    OrdenesTrabajo, OrdenTrabajoCreate, OrdenTrabajoUpdate, OrdenTrabajoOut,
    OrdenTrabajoSucursalOut, OrdenTrabajoClienteOut, OrdenTrabajoUsuarioOut, OrdenTrabajoPacienteOut, OrdenTrabajoProductoOut
)
from models.cotizacion_model import Cotizaciones, CotizacionDetalle
from models.info_referencial_model import InfoReferencial, InfoReferencialOut
from models.sucursales_model import Sucursal
from models.users_model import User
from models.clientes_model import Cliente
from models.pacientes_model import Paciente

router = APIRouter(prefix="/ordenes-trabajo", tags=["Ordenes de Trabajo"], dependencies=[Depends(get_current_user)])

_ORDEN_RELATIONS = (
    selectinload(OrdenesTrabajo.sucursal),
    selectinload(OrdenesTrabajo.cliente),
    selectinload(OrdenesTrabajo.usuario),
    selectinload(OrdenesTrabajo.paciente),
    selectinload(OrdenesTrabajo.cotizacion).selectinload(Cotizaciones.detalles).selectinload(CotizacionDetalle.producto),
)


async def _get_info_referencial(db: AsyncSession, cliente_id: int, paciente_id: int | None):
    if not paciente_id:
        return None
    result = await db.execute(
        select(InfoReferencial)
        .where(InfoReferencial.cliente_id == cliente_id, InfoReferencial.paciente_id == paciente_id)
        .order_by(InfoReferencial.fecha.desc())
    )
    return result.scalars().first()


async def _build_orden_trabajo_out(orden: OrdenesTrabajo, db: AsyncSession) -> OrdenTrabajoOut:
    if not orden.cotizacion:
        raise HTTPException(status_code=400, detail="La orden de trabajo no tiene una cotizacion asociada")

    info_referencial = await _get_info_referencial(db, orden.id_cliente, orden.id_paciente)

    detalles = [
        OrdenTrabajoProductoOut(
            nombre=detalle.producto.nombre,
            codigo_externo=detalle.producto.codigo_externo,
            cantidad=detalle.cantidad
        )
        for detalle in orden.cotizacion.detalles
    ]

    return OrdenTrabajoOut(
        id=orden.id,
        sucursal=OrdenTrabajoSucursalOut.model_validate(orden.sucursal),
        cliente=OrdenTrabajoClienteOut.model_validate(orden.cliente),
        usuario=OrdenTrabajoUsuarioOut.model_validate(orden.usuario),
        paciente=OrdenTrabajoPacienteOut.model_validate(orden.paciente) if orden.paciente else None,
        info_referencial=InfoReferencialOut.model_validate(info_referencial) if info_referencial else None,
        promesa_entrega=orden.cotizacion.promesa_entrega,
        fecha=orden.cotizacion.fecha,
        detalles=detalles
    )


@router.post('/create', response_model=OrdenTrabajoOut)
async def create_orden_trabajo(orden: OrdenTrabajoCreate, db: AsyncSession = Depends(get_db)):
    try:
        sucursal_result = await db.execute(select(Sucursal).where(Sucursal.id == orden.sucursal_id))
        if not sucursal_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")

        usuario_result = await db.execute(select(User).where(User.id == orden.usuario_id))
        if not usuario_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        cliente_result = await db.execute(select(Cliente).where(Cliente.id == orden.id_cliente))
        if not cliente_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        if orden.id_paciente is not None:
            paciente_result = await db.execute(select(Paciente).where(Paciente.id == orden.id_paciente))
            if not paciente_result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Paciente no encontrado")

        if orden.id_cotizacion is not None:
            cotizacion_result = await db.execute(select(Cotizaciones).where(Cotizaciones.id == orden.id_cotizacion))
            if not cotizacion_result.scalar_one_or_none():
                raise HTTPException(status_code=404, detail="Cotizacion no encontrada")

        nueva_orden = OrdenesTrabajo(**orden.model_dump())
        db.add(nueva_orden)
        await db.commit()

        result = await db.execute(
            select(OrdenesTrabajo).options(*_ORDEN_RELATIONS).where(OrdenesTrabajo.id == nueva_orden.id)
        )
        return await _build_orden_trabajo_out(result.scalar_one(), db)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/all', response_model=list[OrdenTrabajoOut])
async def get_all_ordenes_trabajo(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(OrdenesTrabajo).options(*_ORDEN_RELATIONS))
        return [await _build_orden_trabajo_out(orden, db) for orden in result.scalars().all()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/cliente/{id_cliente}', response_model=list[OrdenTrabajoOut])
async def get_ordenes_trabajo_by_cliente(id_cliente: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(OrdenesTrabajo).options(*_ORDEN_RELATIONS).where(OrdenesTrabajo.id_cliente == id_cliente)
        )
        return [await _build_orden_trabajo_out(orden, db) for orden in result.scalars().all()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/{orden_id}', response_model=OrdenTrabajoOut)
async def get_orden_trabajo(orden_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(OrdenesTrabajo).options(*_ORDEN_RELATIONS).where(OrdenesTrabajo.id == orden_id)
        )
        orden = result.scalar_one_or_none()
        if not orden:
            raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")
        return await _build_orden_trabajo_out(orden, db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.put('/update/{orden_id}', response_model=OrdenTrabajoOut)
async def update_orden_trabajo(orden_id: int, orden_update: OrdenTrabajoUpdate, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(OrdenesTrabajo).options(*_ORDEN_RELATIONS).where(OrdenesTrabajo.id == orden_id)
        )
        orden = result.scalar_one_or_none()
        if not orden:
            raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

        for field, value in orden_update.model_dump(exclude_unset=True).items():
            setattr(orden, field, value)

        db.add(orden)
        await db.commit()

        result = await db.execute(
            select(OrdenesTrabajo).options(*_ORDEN_RELATIONS).where(OrdenesTrabajo.id == orden_id)
        )
        return await _build_orden_trabajo_out(result.scalar_one(), db)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")
