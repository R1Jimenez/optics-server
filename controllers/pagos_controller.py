from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func, exists, update
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.abonos_model import Abonos, AbonoOut, TIPO_PAGO, TIPO_INCOBRABLE
from models.cotizacion_model import Cotizaciones, CotizacionDetalle
from models.sucursales_model import Sucursal
from models.tipo_venta_model import TipoVenta
from models.pagos_model import (
    Pagos, PagoForma, PagoFormaIn, PagoInicialCreate, AbonosCobro, PagoOut, PagoFormaOut,
    PagoInicialPendienteOut, PagoInicialProductoOut, PagoParcialOut,
    LiquidacionOut, LiquidacionesPaginaOut, LiquidacionDetalleOut, LiquidacionPagoOut,
    FORMAS_PAGO, EFECTIVO, TIPO_PAGO_INICIAL, TIPO_ABONO
)

router = APIRouter(prefix="/pagos", tags=["Pagos"], dependencies=[Depends(get_current_user)])


def _pendiente_pago_inicial():
    """Condicion SQL: presupuesto activo con pago inicial por cobrar."""
    return (
        Cotizaciones.active.is_(True),
        Cotizaciones.pago_inicial > 0,
        Cotizaciones.pago_inicial_pago_id.is_(None),
    )


def con_saldo(es_credito: bool | None = None):
    """Condicion SQL: venta activa con saldo y pago inicial ya cobrado (o sin pago inicial).
    es_credito filtra por tipo de venta; None incluye todas."""
    condiciones = [
        Cotizaciones.active.is_(True),
        Cotizaciones.pago_restante > 0,
        or_(Cotizaciones.pago_inicial <= 0, Cotizaciones.pago_inicial_pago_id.is_not(None)),
    ]
    if es_credito is not None:
        condiciones.append(Cotizaciones.tipo_venta_rel.has(TipoVenta.es_credito.is_(es_credito)))
    return tuple(condiciones)


def _productos(c: Cotizaciones) -> list[PagoInicialProductoOut]:
    return [
        PagoInicialProductoOut(
            nombre=d.producto.nombre if d.producto else f"Producto #{d.producto_id}",
            cantidad=d.cantidad,
            subtotal=d.subtotal,
        )
        for d in c.detalles
    ]


def liquidada():
    """Condicion SQL: venta activa pagada por completo (no cuenta si el saldo se cancelo como incobrable)."""
    return (
        Cotizaciones.active.is_(True),
        Cotizaciones.pago_restante <= 0,
        or_(Cotizaciones.pago_inicial <= 0, Cotizaciones.pago_inicial_pago_id.is_not(None)),
        ~exists().where(Abonos.cotizacion_id == Cotizaciones.id, Abonos.tipo == TIPO_INCOBRABLE),
    )


def _fecha_liquidacion():
    """Fecha del ultimo pago: el abono mas reciente o el cobro del pago inicial."""
    ultimo_abono = (
        select(func.max(Abonos.fecha))
        .where(Abonos.cotizacion_id == Cotizaciones.id, Abonos.tipo == TIPO_PAGO)
        .scalar_subquery()
    )
    pago_inicial = select(Pagos.fecha).where(Pagos.id == Cotizaciones.pago_inicial_pago_id).scalar_subquery()
    # GREATEST de PostgreSQL ignora los NULL
    return func.coalesce(func.greatest(ultimo_abono, pago_inicial), Cotizaciones.fecha)


def _ticket_liquidacion():
    """Cobro de caja con el que se termino de pagar la venta."""
    ultimo_cobro = (
        select(Abonos.pago_id)
        .where(Abonos.cotizacion_id == Cotizaciones.id, Abonos.tipo == TIPO_PAGO, Abonos.pago_id.is_not(None))
        .order_by(Abonos.fecha.desc(), Abonos.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    return func.coalesce(ultimo_cobro, Cotizaciones.pago_inicial_pago_id)


# ---------- Reglas de negocio (sin acceso a BD) ----------

def calcular_cobro(total: Decimal, formas: list[PagoFormaIn]) -> tuple[Decimal, Decimal]:
    """Valida las formas de pago y devuelve (recibido, cambio). El cambio solo puede salir del efectivo."""
    vistas = set()
    for f in formas:
        if f.forma not in FORMAS_PAGO:
            raise HTTPException(status_code=400, detail=f"Forma de pago no valida: {f.forma}")
        if f.forma in vistas:
            raise HTTPException(status_code=400, detail=f"La forma de pago {f.forma} esta repetida")
        vistas.add(f.forma)

    recibido = sum((f.importe for f in formas), Decimal("0"))
    if recibido < total:
        raise HTTPException(status_code=400, detail=f"El importe recibido (${recibido:.2f}) no cubre el total a pagar (${total:.2f})")

    cambio = recibido - total
    efectivo = sum((f.importe for f in formas if f.forma == EFECTIVO), Decimal("0"))
    if cambio > efectivo:
        raise HTTPException(
            status_code=400,
            detail=f"El excedente de ${cambio:.2f} solo puede entregarse como cambio en efectivo (efectivo recibido: ${efectivo:.2f})"
        )
    return recibido, cambio


def _salida(pago: Pagos, cotizacion_ids: list[int]) -> PagoOut:
    return PagoOut(
        id=pago.id,
        tipo=pago.tipo,
        cliente_id=pago.cliente_id,
        sucursal_id=pago.sucursal_id,
        fecha=pago.fecha,
        total=pago.total,
        recibido=pago.recibido,
        cambio=pago.cambio,
        observaciones=pago.observaciones,
        formas=[PagoFormaOut.model_validate(f) for f in pago.formas],
        cotizacion_ids=cotizacion_ids,
    )


# ---------- Endpoints ----------

@router.get("/formas", response_model=list[str])
async def get_formas_pago():
    return FORMAS_PAGO


@router.get("/pago-inicial/cliente/{id_cliente}", response_model=list[PagoInicialPendienteOut])
async def pagos_iniciales_pendientes(id_cliente: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(
                selectinload(Cotizaciones.tipo_venta_rel),
                selectinload(Cotizaciones.plazo_rel),
                selectinload(Cotizaciones.detalles).selectinload(CotizacionDetalle.producto),
            )
            .where(Cotizaciones.id_cliente == id_cliente, *_pendiente_pago_inicial())
            .order_by(Cotizaciones.fecha.asc(), Cotizaciones.id.asc())
        )
        return [
            PagoInicialPendienteOut(
                id=c.id,
                tipo_venta=c.tipo_venta_rel.venta if c.tipo_venta_rel else "-",
                plazo=c.plazo_rel.plazo if c.plazo_rel else "-",
                fecha=c.fecha,
                vencimiento=c.vencimiento,
                total_venta=c.total_venta,
                pago_inicial=c.pago_inicial,
                detalles=_productos(c),
            )
            for c in result.scalars().all()
        ]
    except Exception as e:
        print(f"Error al obtener pagos iniciales pendientes: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/pago-inicial", response_model=PagoOut)
async def cobrar_pago_inicial(
    datos: PagoInicialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        ids = list(dict.fromkeys(datos.cotizacion_ids))
        if not await db.scalar(select(Sucursal.id).where(Sucursal.id == datos.sucursal_id)):
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")

        # FOR UPDATE evita cobrar dos veces el mismo pago inicial
        result = await db.execute(
            select(Cotizaciones).where(Cotizaciones.id.in_(ids)).order_by(Cotizaciones.id).with_for_update()
        )
        cotizaciones = result.scalars().all()
        faltantes = set(ids) - {c.id for c in cotizaciones}
        if faltantes:
            raise HTTPException(status_code=404, detail=f"Presupuesto no encontrado: {', '.join(map(str, sorted(faltantes)))}")

        clientes = {c.id_cliente for c in cotizaciones}
        if len(clientes) > 1:
            raise HTTPException(status_code=400, detail="Todos los presupuestos deben ser del mismo cliente")
        for c in cotizaciones:
            if not c.active:
                raise HTTPException(status_code=400, detail=f"El presupuesto {c.id} no esta activo")
            if c.pago_inicial_pago_id is not None:
                raise HTTPException(status_code=400, detail=f"El pago inicial del presupuesto {c.id} ya fue cobrado")
            if c.pago_inicial <= 0:
                raise HTTPException(status_code=400, detail=f"El presupuesto {c.id} no tiene pago inicial por cobrar")

        total = sum((c.pago_inicial for c in cotizaciones), Decimal("0"))
        recibido, cambio = calcular_cobro(total, datos.formas)

        observaciones = (datos.observaciones or "").strip() or None
        pago = Pagos(
            tipo=TIPO_PAGO_INICIAL,
            cliente_id=clientes.pop(),
            sucursal_id=datos.sucursal_id,
            usuario_id=current_user["id"],
            total=total,
            recibido=recibido,
            cambio=cambio,
            observaciones=observaciones,
            formas=[
                PagoForma(forma=f.forma, referencia=(f.referencia or "").strip() or None, importe=f.importe)
                for f in datos.formas
            ],
        )
        db.add(pago)
        await db.flush()
        cobradas = [c.id for c in cotizaciones]
        for c in cotizaciones:
            c.pago_inicial_pago_id = pago.id
        pago_id = pago.id
        await db.commit()

        result = await db.execute(select(Pagos).options(selectinload(Pagos.formas)).where(Pagos.id == pago_id))
        return _salida(result.scalar_one(), cobradas)
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al cobrar pago inicial: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/parciales/cliente/{id_cliente}", response_model=list[PagoParcialOut])
async def pagos_parciales_pendientes(id_cliente: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(
                selectinload(Cotizaciones.tipo_venta_rel),
                selectinload(Cotizaciones.plazo_rel),
                selectinload(Cotizaciones.detalles).selectinload(CotizacionDetalle.producto),
            )
            .where(Cotizaciones.id_cliente == id_cliente, *con_saldo())
            .order_by(Cotizaciones.fecha.asc(), Cotizaciones.id.asc())
        )
        cotizaciones = result.scalars().all()
        if not cotizaciones:
            return []

        abonos_result = await db.execute(
            select(Abonos).where(Abonos.cotizacion_id.in_([c.id for c in cotizaciones])).order_by(Abonos.fecha.asc())
        )
        abonos: dict[int, list[Abonos]] = {}
        for a in abonos_result.scalars().all():
            abonos.setdefault(a.cotizacion_id, []).append(a)

        salida = []
        for c in cotizaciones:
            propios = abonos.get(c.id, [])
            # lo pagado incluye el pago inicial cobrado en caja
            pagado = c.pago_inicial + sum((a.monto for a in propios if a.tipo == TIPO_PAGO), Decimal("0"))
            salida.append(PagoParcialOut(
                id=c.id,
                tipo_venta=c.tipo_venta_rel.venta if c.tipo_venta_rel else "-",
                plazo=c.plazo_rel.plazo if c.plazo_rel else "-",
                fecha=c.fecha,
                total_venta=c.total_venta,
                pago_inicial=c.pago_inicial,
                total_pagado=pagado,
                diferencia=c.pago_restante,
                detalles=_productos(c),
                abonos=[AbonoOut.model_validate(a) for a in propios],
            ))
        return salida
    except Exception as e:
        print(f"Error al obtener pagos parciales: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/abonos", response_model=PagoOut)
async def cobrar_abonos(
    datos: AbonosCobro,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        ids = [a.cotizacion_id for a in datos.abonos]
        if len(set(ids)) != len(ids):
            raise HTTPException(status_code=400, detail="Un presupuesto aparece mas de una vez en los abonos")
        if not await db.scalar(select(Sucursal.id).where(Sucursal.id == datos.sucursal_id)):
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")

        # FOR UPDATE evita que dos cobros simultaneos dejen el saldo inconsistente
        result = await db.execute(
            select(Cotizaciones).where(Cotizaciones.id.in_(ids)).order_by(Cotizaciones.id).with_for_update()
        )
        cotizaciones = {c.id: c for c in result.scalars().all()}
        faltantes = sorted(set(ids) - cotizaciones.keys())
        if faltantes:
            raise HTTPException(status_code=404, detail=f"Presupuesto no encontrado: {', '.join(map(str, faltantes))}")

        clientes = {c.id_cliente for c in cotizaciones.values()}
        if len(clientes) > 1:
            raise HTTPException(status_code=400, detail="Todos los presupuestos deben ser del mismo cliente")
        for item in datos.abonos:
            c = cotizaciones[item.cotizacion_id]
            if not c.active:
                raise HTTPException(status_code=400, detail=f"El presupuesto {c.id} no esta activo")
            if c.pago_inicial > 0 and c.pago_inicial_pago_id is None:
                raise HTTPException(status_code=400, detail=f"Primero cobre el pago inicial del presupuesto {c.id}")
            if item.monto > c.pago_restante:
                raise HTTPException(
                    status_code=400,
                    detail=f"El abono de ${item.monto:.2f} excede el saldo de ${c.pago_restante:.2f} del presupuesto {c.id}"
                )

        total = sum((a.monto for a in datos.abonos), Decimal("0"))
        recibido, cambio = calcular_cobro(total, datos.formas)

        pago = Pagos(
            tipo=TIPO_ABONO,
            cliente_id=clientes.pop(),
            sucursal_id=datos.sucursal_id,
            usuario_id=current_user["id"],
            total=total,
            recibido=recibido,
            cambio=cambio,
            observaciones=(datos.observaciones or "").strip() or None,
            formas=[
                PagoForma(forma=f.forma, referencia=(f.referencia or "").strip() or None, importe=f.importe)
                for f in datos.formas
            ],
        )
        db.add(pago)
        await db.flush()
        for item in datos.abonos:
            c = cotizaciones[item.cotizacion_id]
            c.pago_restante = c.pago_restante - item.monto
            db.add(Abonos(cotizacion_id=c.id, usuario_id=current_user["id"], monto=item.monto, tipo=TIPO_PAGO, pago_id=pago.id))
        pago_id = pago.id
        await db.commit()

        result = await db.execute(select(Pagos).options(selectinload(Pagos.formas)).where(Pagos.id == pago_id))
        return _salida(result.scalar_one(), ids)
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al cobrar abonos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/liquidaciones/cliente/{id_cliente}", response_model=LiquidacionesPaginaOut)
async def liquidaciones_cliente(
    id_cliente: int,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        fecha = _fecha_liquidacion().label("fecha_liquidacion")
        # el total viaja en cada fila (COUNT OVER) para resolver la pagina en una sola consulta
        result = await db.execute(
            select(
                Cotizaciones.id, Sucursal.sucursal, Cotizaciones.total_venta, Cotizaciones.liquidacion_impresa,
                _ticket_liquidacion().label("ticket"), fecha, func.count().over().label("total"),
            )
            .join(Sucursal, Sucursal.id == Cotizaciones.sucursal_id)
            .where(Cotizaciones.id_cliente == id_cliente, *liquidada())
            .order_by(fecha.desc(), Cotizaciones.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        filas = result.all()
        if filas:
            total = filas[0].total
        else:
            total = await db.scalar(
                select(func.count()).select_from(Cotizaciones).where(Cotizaciones.id_cliente == id_cliente, *liquidada())
            ) if pagina > 1 else 0

        items = [
            LiquidacionOut(
                id=f.id, sucursal=f.sucursal, ticket=f.ticket, folio=None, importe_total=f.total_venta,
                impresa=f.liquidacion_impresa, fecha_liquidacion=f.fecha_liquidacion,
            )
            for f in filas
        ]
        return LiquidacionesPaginaOut(total=total, pagina=pagina, por_pagina=por_pagina, items=items)
    except Exception as e:
        print(f"Error al obtener liquidaciones: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/liquidaciones/{cotizacion_id}", response_model=LiquidacionDetalleOut)
async def detalle_liquidacion(cotizacion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones, _fecha_liquidacion().label("fecha_liquidacion"))
            .options(
                selectinload(Cotizaciones.sucursal),
                selectinload(Cotizaciones.tipo_venta_rel),
                selectinload(Cotizaciones.plazo_rel),
                selectinload(Cotizaciones.detalles).selectinload(CotizacionDetalle.producto),
            )
            .where(Cotizaciones.id == cotizacion_id, *liquidada())
        )
        fila = result.first()
        if not fila:
            raise HTTPException(status_code=404, detail="La venta no existe o no esta liquidada")
        c, fecha_liquidacion = fila

        abonos = (await db.execute(
            select(Abonos).where(Abonos.cotizacion_id == c.id, Abonos.tipo == TIPO_PAGO).order_by(Abonos.fecha, Abonos.id)
        )).scalars().all()
        cobro_ids = {a.pago_id for a in abonos if a.pago_id} | ({c.pago_inicial_pago_id} if c.pago_inicial_pago_id else set())
        cobros = {}
        if cobro_ids:
            cobros = {
                p.id: p for p in (await db.execute(
                    select(Pagos).options(selectinload(Pagos.formas)).where(Pagos.id.in_(cobro_ids))
                )).scalars().all()
            }

        def _pago(concepto, fecha, monto, cobro_id):
            cobro = cobros.get(cobro_id)
            return LiquidacionPagoOut(
                concepto=concepto, fecha=fecha, monto=monto, cobro_id=cobro_id,
                cobro_total=cobro.total if cobro else None,
                formas=[PagoFormaOut.model_validate(f) for f in cobro.formas] if cobro else [],
            )

        pagos = []
        if c.pago_inicial > 0:
            inicial = cobros.get(c.pago_inicial_pago_id)
            pagos.append(_pago("Pago inicial", inicial.fecha if inicial else c.fecha, c.pago_inicial, c.pago_inicial_pago_id))
        pagos += [_pago("Abono", a.fecha, a.monto, a.pago_id) for a in abonos]

        return LiquidacionDetalleOut(
            id=c.id,
            sucursal=c.sucursal.sucursal if c.sucursal else "-",
            tipo_venta=c.tipo_venta_rel.venta if c.tipo_venta_rel else "-",
            plazo=c.plazo_rel.plazo if c.plazo_rel else "-",
            fecha_venta=c.fecha,
            fecha_liquidacion=fecha_liquidacion,
            total_venta=c.total_venta,
            impresa=c.liquidacion_impresa,
            detalles=_productos(c),
            pagos=pagos,
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener detalle de liquidacion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/liquidaciones/{cotizacion_id}/impresa")
async def marcar_liquidacion_impresa(cotizacion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            update(Cotizaciones)
            .where(Cotizaciones.id == cotizacion_id, *liquidada())
            .values(liquidacion_impresa=True)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="La venta no existe o no esta liquidada")
        await db.commit()
        return {"id": cotizacion_id, "impresa": True}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al marcar liquidacion impresa: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
