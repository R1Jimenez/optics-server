from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.abonos_model import (
    Abonos, AbonosAplicar, AbonoOut, CuentaPorCobrarOut, CuentaPorCobrarProductoOut,
    TIPO_PAGO, TIPO_INCOBRABLE
)
from models.cotizacion_model import Cotizaciones, CotizacionDetalle

router = APIRouter(prefix="/abonos", tags=["Abonos"], dependencies=[Depends(get_current_user)])


async def _get_cotizacion_bloqueada(db: AsyncSession, cotizacion_id: int) -> Cotizaciones:
    # FOR UPDATE evita que dos cobros simultaneos dejen el saldo inconsistente
    result = await db.execute(
        select(Cotizaciones).where(Cotizaciones.id == cotizacion_id).with_for_update()
    )
    cotizacion = result.scalar_one_or_none()
    if not cotizacion or not cotizacion.active:
        raise HTTPException(status_code=404, detail=f"La cotizacion {cotizacion_id} no existe o no esta activa")
    return cotizacion


@router.get('/cuentas-por-cobrar/cliente/{id_cliente}', response_model=list[CuentaPorCobrarOut])
async def get_cuentas_por_cobrar(id_cliente: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(
                selectinload(Cotizaciones.tipo_venta_rel),
                selectinload(Cotizaciones.detalles).selectinload(CotizacionDetalle.producto),
            )
            .where(
                Cotizaciones.id_cliente == id_cliente,
                Cotizaciones.active.is_(True),
                Cotizaciones.pago_restante > 0
            )
            .order_by(Cotizaciones.vencimiento.asc().nulls_last(), Cotizaciones.id.asc())
        )
        cotizaciones = result.scalars().all()
        if not cotizaciones:
            return []

        abonos_result = await db.execute(
            select(Abonos)
            .where(Abonos.cotizacion_id.in_([c.id for c in cotizaciones]))
            .order_by(Abonos.fecha.asc())
        )
        abonos_por_cotizacion: dict[int, list[Abonos]] = {}
        for abono in abonos_result.scalars().all():
            abonos_por_cotizacion.setdefault(abono.cotizacion_id, []).append(abono)

        cuentas = []
        for c in cotizaciones:
            abonos = abonos_por_cotizacion.get(c.id, [])
            total_pagado = sum((a.monto for a in abonos if a.tipo == TIPO_PAGO), Decimal("0"))
            cuentas.append(CuentaPorCobrarOut(
                id=c.id,
                concepto=f"Venta {c.tipo_venta_rel.venta}" if c.tipo_venta_rel else "Venta",
                emision=c.fecha,
                vencimiento=c.vencimiento,
                importe=c.total_venta - c.pago_inicial,
                total_pagado=total_pagado,
                diferencia=c.pago_restante,
                detalles=[
                    CuentaPorCobrarProductoOut(
                        producto_id=d.producto_id,
                        nombre=d.producto.nombre if d.producto else f"Producto #{d.producto_id}",
                        cantidad=d.cantidad,
                        subtotal=d.subtotal
                    )
                    for d in c.detalles
                ],
                abonos=[AbonoOut.model_validate(a) for a in abonos]
            ))
        return cuentas
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/cotizacion/{cotizacion_id}', response_model=list[AbonoOut])
async def get_abonos_cotizacion(cotizacion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Abonos).where(Abonos.cotizacion_id == cotizacion_id).order_by(Abonos.fecha.asc())
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.post('/aplicar', response_model=list[AbonoOut])
async def aplicar_abonos(
    datos: AbonosAplicar,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        nuevos = []
        for item in datos.abonos:
            cotizacion = await _get_cotizacion_bloqueada(db, item.cotizacion_id)
            if item.monto > cotizacion.pago_restante:
                raise HTTPException(
                    status_code=400,
                    detail=f"El abono de ${item.monto} excede el saldo de ${cotizacion.pago_restante} de la cotizacion {cotizacion.id}"
                )
            cotizacion.pago_restante = cotizacion.pago_restante - item.monto
            nuevos.append(Abonos(
                cotizacion_id=cotizacion.id,
                usuario_id=current_user["id"],
                monto=item.monto,
                tipo=TIPO_PAGO
            ))

        db.add_all(nuevos)
        await db.commit()
        for abono in nuevos:
            await db.refresh(abono)
        return nuevos
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.post('/incobrable/{cotizacion_id}', response_model=AbonoOut)
async def marcar_incobrable(
    cotizacion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        cotizacion = await _get_cotizacion_bloqueada(db, cotizacion_id)
        if cotizacion.pago_restante <= 0:
            raise HTTPException(status_code=400, detail="La cotizacion no tiene saldo pendiente")

        castigo = Abonos(
            cotizacion_id=cotizacion.id,
            usuario_id=current_user["id"],
            monto=cotizacion.pago_restante,
            tipo=TIPO_INCOBRABLE
        )
        cotizacion.pago_restante = Decimal("0")

        db.add(castigo)
        await db.commit()
        await db.refresh(castigo)
        return castigo
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")
