import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.abonos_model import Abonos
from models.cotizacion_model import (
    Cotizaciones, CotizacionDetalle, CotizacionCreate, CotizacionUpdate, CotizacionOut, CotizacionEnEsperaOut,
    TicketsPaginaOut, TicketResumenOut, TicketOut, TicketItemOut
)
from models.inventario_model import (
    InventarioSucursal, InventarioMovimiento,
    TIPO_SALIDA_VENTA, TIPO_ENTRADA_MODIFICACION_VENTA, TIPO_ENTRADA_CANCELACION_VENTA
)
from models.precios_sucursal_model import PreciosSucursal
from models.clientes_model import Cliente
from models.tipo_cliente_model import Tipo_Cliente
from models.ordenes_trabajo_model import OrdenesTrabajo
from models.plazo_model import Plazo
from models.producto_model import ProductoAtributo
from models.promociones_model import Promociones
from controllers.promociones_controller import (
    obtener_promocion_aplicable, cargar_promocion, condiciones_por_categoria, producto_elegible, porcentaje_descuento
)

router = APIRouter(prefix="/cotizacion", tags=["Cotizaciones"], dependencies=[Depends(get_current_user)])


def _calcular_vencimiento(fecha_inicio: datetime, plazo_texto: str) -> datetime:
    """Extrae el numero de semanas del texto del plazo (ej. '4 semanas') y lo suma a la fecha de inicio."""
    match = re.search(r"\d+", plazo_texto)
    if not match:
        raise HTTPException(status_code=400, detail=f"No se pudo determinar el numero de semanas del plazo '{plazo_texto}'")
    semanas = int(match.group())
    return fecha_inicio + timedelta(weeks=semanas)


def _referencia_presupuesto(cotizacion_id: int) -> str:
    return f"Presupuesto {cotizacion_id}"


async def _aplicar_descuentos(db: AsyncSession, detalles, pct_cliente, promocion, cond) -> Decimal:
    """Asigna descuento_porcentaje a cada renglon (tipo de cliente + promocion) y devuelve el total de la venta."""
    valores: dict[int, set[int]] = {}
    if cond and cond["atributos_valores"]:
        filas = await db.execute(
            select(ProductoAtributo.producto_id, ProductoAtributo.atributovalor_id)
            .where(ProductoAtributo.producto_id.in_({d.producto_id for d in detalles}))
        )
        for producto_id, valor_id in filas.all():
            valores.setdefault(producto_id, set()).add(valor_id)

    total = Decimal("0")
    for d in detalles:
        elegible = bool(cond) and producto_elegible(cond, d.producto_id, valores.get(d.producto_id, set()))
        pct = porcentaje_descuento(
            pct_cliente,
            promocion.descuento if promocion else None,
            bool(promocion and promocion.acumulativa),
            elegible
        )
        d.descuento_porcentaje = pct
        total += Decimal(d.subtotal) * (Decimal("100") - pct) / Decimal("100")
    return total.quantize(Decimal("0.01"))


@router.post('/create', response_model=CotizacionOut)
async def create_cotizacion(
    cotizacion: CotizacionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        if not cotizacion.productos:
            raise HTTPException(status_code=400, detail="Debe incluir al menos un producto en la cotizacion")

        cliente_result = await db.execute(select(Cliente).where(Cliente.id == cotizacion.id_cliente))
        cliente = cliente_result.scalar_one_or_none()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        tipo_cliente_result = await db.execute(select(Tipo_Cliente).where(Tipo_Cliente.id == cliente.tipocliente))
        tipo_cliente = tipo_cliente_result.scalar_one_or_none()
        if not tipo_cliente:
            raise HTTPException(status_code=400, detail="El cliente no tiene un tipo de cliente valido asignado")

        plazo_result = await db.execute(select(Plazo).where(Plazo.id == cotizacion.plazo))
        plazo_obj = plazo_result.scalar_one_or_none()
        if not plazo_obj:
            raise HTTPException(status_code=404, detail="Plazo no encontrado")

        promocion = cond = None
        if cotizacion.promocion_id is not None:
            promocion, cond = await obtener_promocion_aplicable(
                db, cotizacion.promocion_id, cotizacion.sucursal_id, cotizacion.tipo_venta,
                cotizacion.plazo, cotizacion.id_cliente
            )

        detalles = []
        movimientos = []
        total_normal = Decimal("0")

        for item in cotizacion.productos:
            inv_result = await db.execute(
                select(InventarioSucursal).where(
                    InventarioSucursal.sucursal_id == cotizacion.sucursal_id,
                    InventarioSucursal.producto_id == item.producto_id
                )
            )
            inventario = inv_result.scalar_one_or_none()
            if not inventario or inventario.existencia_actual < item.cantidad:
                raise HTTPException(
                    status_code=400,
                    detail=f"Existencia insuficiente para el producto {item.producto_id} en la sucursal {cotizacion.sucursal_id}"
                )

            precio_result = await db.execute(
                select(PreciosSucursal).where(
                    PreciosSucursal.sucursal == cotizacion.sucursal_id,
                    PreciosSucursal.producto == item.producto_id
                )
            )
            precio_sucursal = precio_result.scalar_one_or_none()
            if not precio_sucursal:
                raise HTTPException(
                    status_code=400,
                    detail=f"No hay precio configurado para el producto {item.producto_id} en la sucursal {cotizacion.sucursal_id}"
                )

            precio_unitario = Decimal(str(precio_sucursal.precio))
            subtotal = precio_unitario * item.cantidad
            total_normal += subtotal

            detalles.append(CotizacionDetalle(
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=precio_unitario,
                subtotal=subtotal
            ))

            # descontar la existencia vendida y dejar registro del movimiento
            existencia_final = inventario.existencia_actual - item.cantidad
            inventario.existencia_actual = existencia_final
            movimientos.append(InventarioMovimiento(
                inventario_id=inventario.id,
                entrada=0,
                merma=item.cantidad,
                existencia_final=existencia_final,
                tipo=TIPO_SALIDA_VENTA,
                usuario_id=current_user["id"]
            ))

        total_venta = await _aplicar_descuentos(db, detalles, tipo_cliente.porcentaje_descuento, promocion, cond)
        pago_restante = total_venta - cotizacion.pago_inicial

        fecha_actual = datetime.utcnow()

        nueva_cotizacion = Cotizaciones(
            sucursal_id=cotizacion.sucursal_id,
            usuario_id=cotizacion.usuario_id,
            id_cliente=cotizacion.id_cliente,
            id_paciente=cotizacion.id_paciente,
            tipo_venta=cotizacion.tipo_venta,
            plazo=cotizacion.plazo,
            promocion_id=cotizacion.promocion_id,
            pago_inicial=cotizacion.pago_inicial,
            pago_restante=pago_restante,
            fecha=fecha_actual,
            promesa_entrega=cotizacion.promesa_entrega,
            vencimiento=_calcular_vencimiento(fecha_actual, plazo_obj.plazo),
            total_normal=total_normal,
            total_venta=total_venta,
            detalles=detalles
        )

        db.add(nueva_cotizacion)
        db.add_all(movimientos)
        await db.flush()

        for movimiento in movimientos:
            movimiento.referencia = _referencia_presupuesto(nueva_cotizacion.id)

        # cada venta (cotizacion) genera automaticamente su orden de trabajo
        nueva_orden = OrdenesTrabajo(
            sucursal_id=cotizacion.sucursal_id,
            usuario_id=cotizacion.usuario_id,
            id_cliente=cotizacion.id_cliente,
            id_paciente=cotizacion.id_paciente,
            id_cotizacion=nueva_cotizacion.id
        )
        db.add(nueva_orden)
        await db.commit()

        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id == nueva_cotizacion.id)
        )
        return result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/all', response_model=list[CotizacionOut])
async def get_all_cotizaciones(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones).options(selectinload(Cotizaciones.detalles))
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


def _a_utc_naive(fecha: datetime) -> datetime:
    # las fechas se guardan en UTC sin zona horaria
    if fecha.tzinfo is None:
        return fecha
    return fecha.astimezone(timezone.utc).replace(tzinfo=None)


@router.get('/tickets', response_model=TicketsPaginaOut)
async def listar_tickets(
    folio: int | None = Query(None),
    id_cliente: int | None = Query(None),
    desde: datetime | None = Query(None),
    hasta: datetime | None = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Cotizaciones, Cliente).join(Cliente, Cliente.id == Cotizaciones.id_cliente)
        if folio is not None:
            query = query.where(Cotizaciones.id == folio)
        if id_cliente is not None:
            query = query.where(Cotizaciones.id_cliente == id_cliente)
        if desde is not None:
            query = query.where(Cotizaciones.fecha >= _a_utc_naive(desde))
        if hasta is not None:
            query = query.where(Cotizaciones.fecha < _a_utc_naive(hasta))

        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(
            query.order_by(Cotizaciones.fecha.desc(), Cotizaciones.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )

        items = [
            TicketResumenOut(
                id=cotizacion.id,
                fecha=cotizacion.fecha,
                cliente=f"{cliente.nombres} {cliente.apellidos}",
                importe=cotizacion.total_venta
            )
            for cotizacion, cliente in result.all()
        ]
        return TicketsPaginaOut(total=total, pagina=pagina, por_pagina=por_pagina, items=items)
    except Exception as e:
        print(f"Error al listar tickets: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get('/ticket/{cotizacion_id}', response_model=TicketOut)
async def get_ticket(cotizacion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(
                selectinload(Cotizaciones.sucursal),
                selectinload(Cotizaciones.usuario),
                selectinload(Cotizaciones.cliente),
                selectinload(Cotizaciones.paciente),
                selectinload(Cotizaciones.plazo_rel),
                selectinload(Cotizaciones.detalles).selectinload(CotizacionDetalle.producto),
            )
            .where(Cotizaciones.id == cotizacion_id)
        )
        cotizacion = result.scalar_one_or_none()
        if not cotizacion:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")

        cliente = cotizacion.cliente
        tipo_cliente = None
        if cliente.tipocliente is not None:
            tipo_result = await db.execute(select(Tipo_Cliente).where(Tipo_Cliente.id == cliente.tipocliente))
            tipo_cliente = tipo_result.scalar_one_or_none()

        # se deriva de los totales guardados para que coincida con el ticket original aunque cambie el tipo de cliente
        descuento_pct = (
            (cotizacion.total_normal - cotizacion.total_venta) * 100 / cotizacion.total_normal
            if cotizacion.total_normal else Decimal("0")
        )
        promocion_nombre = None
        if cotizacion.promocion_id is not None:
            promocion_nombre = await db.scalar(select(Promociones.nombre).where(Promociones.id == cotizacion.promocion_id))

        return TicketOut(
            folio=cotizacion.id,
            fecha=cotizacion.fecha,
            sucursal=cotizacion.sucursal.sucursal if cotizacion.sucursal else "N/A",
            vendedor=f"{cotizacion.usuario.nombres} {cotizacion.usuario.apellidos}" if cotizacion.usuario else "N/A",
            cliente_nombre=f"{cliente.nombres} {cliente.apellidos}",
            cliente_direccion=f"{cliente.calle} {cliente.numero}, {cliente.colonia}, {cliente.ciudad}, {cliente.estado}, CP {cliente.codigopostal}",
            cliente_telefono=cliente.telefono,
            tipo_cliente=tipo_cliente.cliente if tipo_cliente else None,
            paciente=f"{cotizacion.paciente.nombres} {cotizacion.paciente.apellidos}" if cotizacion.paciente else None,
            plazo=cotizacion.plazo_rel.plazo if cotizacion.plazo_rel else None,
            promocion=promocion_nombre,
            items=[
                TicketItemOut(
                    cantidad=d.cantidad,
                    nombre=d.producto.nombre if d.producto else f"Producto #{d.producto_id}",
                    precio_unitario=d.precio_unitario,
                    # ventas anteriores a las promociones no guardan descuento por renglon
                    descuento_porcentaje=d.descuento_porcentaje if d.descuento_porcentaje is not None else round(descuento_pct, 2)
                )
                for d in cotizacion.detalles
            ],
            total_normal=cotizacion.total_normal,
            total_venta=cotizacion.total_venta,
            descuento_porcentaje=round(descuento_pct, 2),
            pago_inicial=cotizacion.pago_inicial,
            pago_restante=cotizacion.total_venta - cotizacion.pago_inicial,
            promesa_entrega=cotizacion.promesa_entrega
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener ticket: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get('/en-espera/{sucursal_id}', response_model=list[CotizacionEnEsperaOut])
async def get_cotizaciones_en_espera(sucursal_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.cliente))
            .where(
                Cotizaciones.sucursal_id == sucursal_id,
                Cotizaciones.active.is_(True),
                Cotizaciones.pago_restante > 0
            )
            .order_by(Cotizaciones.fecha.desc())
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/cliente/{id_cliente}', response_model=list[CotizacionOut])
async def get_cotizaciones_by_cliente(id_cliente: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id_cliente == id_cliente)
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.get('/{cotizacion_id}', response_model=CotizacionOut)
async def get_cotizacion(cotizacion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id == cotizacion_id)
        )
        cotizacion = result.scalar_one_or_none()
        if not cotizacion:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")
        return cotizacion
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.put('/update/{cotizacion_id}', response_model=CotizacionOut)
async def update_cotizacion(
    cotizacion_id: int,
    cotizacion_update: CotizacionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id == cotizacion_id)
        )
        cotizacion = result.scalar_one_or_none()
        if not cotizacion:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")

        sucursal_id = cotizacion_update.sucursal_id if cotizacion_update.sucursal_id is not None else cotizacion.sucursal_id
        id_cliente = cotizacion_update.id_cliente if cotizacion_update.id_cliente is not None else cotizacion.id_cliente

        cliente_result = await db.execute(select(Cliente).where(Cliente.id == id_cliente))
        cliente = cliente_result.scalar_one_or_none()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")

        tipo_cliente_result = await db.execute(select(Tipo_Cliente).where(Tipo_Cliente.id == cliente.tipocliente))
        tipo_cliente = tipo_cliente_result.scalar_one_or_none()
        if not tipo_cliente:
            raise HTTPException(status_code=400, detail="El cliente no tiene un tipo de cliente valido asignado")

        movimientos = []

        if cotizacion_update.productos is not None:
            if not cotizacion_update.productos:
                raise HTTPException(status_code=400, detail="Debe incluir al menos un producto en la cotizacion")

            # devolver al inventario la existencia de los productos que se van a reemplazar
            for detalle in cotizacion.detalles:
                inv_result = await db.execute(
                    select(InventarioSucursal).where(
                        InventarioSucursal.sucursal_id == cotizacion.sucursal_id,
                        InventarioSucursal.producto_id == detalle.producto_id
                    )
                )
                inventario = inv_result.scalar_one_or_none()
                if inventario:
                    existencia_final = inventario.existencia_actual + detalle.cantidad
                    inventario.existencia_actual = existencia_final
                    movimientos.append(InventarioMovimiento(
                        inventario_id=inventario.id,
                        entrada=detalle.cantidad,
                        merma=0,
                        existencia_final=existencia_final,
                        tipo=TIPO_ENTRADA_MODIFICACION_VENTA,
                        referencia=_referencia_presupuesto(cotizacion.id),
                        usuario_id=current_user["id"]
                    ))

            cotizacion.detalles.clear()

            detalles = []
            total_normal = Decimal("0")

            for item in cotizacion_update.productos:
                inv_result = await db.execute(
                    select(InventarioSucursal).where(
                        InventarioSucursal.sucursal_id == sucursal_id,
                        InventarioSucursal.producto_id == item.producto_id
                    )
                )
                inventario = inv_result.scalar_one_or_none()
                if not inventario or inventario.existencia_actual < item.cantidad:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Existencia insuficiente para el producto {item.producto_id} en la sucursal {sucursal_id}"
                    )

                precio_result = await db.execute(
                    select(PreciosSucursal).where(
                        PreciosSucursal.sucursal == sucursal_id,
                        PreciosSucursal.producto == item.producto_id
                    )
                )
                precio_sucursal = precio_result.scalar_one_or_none()
                if not precio_sucursal:
                    raise HTTPException(
                        status_code=400,
                        detail=f"No hay precio configurado para el producto {item.producto_id} en la sucursal {sucursal_id}"
                    )

                precio_unitario = Decimal(str(precio_sucursal.precio))
                subtotal = precio_unitario * item.cantidad
                total_normal += subtotal

                detalles.append(CotizacionDetalle(
                    producto_id=item.producto_id,
                    cantidad=item.cantidad,
                    precio_unitario=precio_unitario,
                    subtotal=subtotal
                ))

                existencia_final = inventario.existencia_actual - item.cantidad
                inventario.existencia_actual = existencia_final
                movimientos.append(InventarioMovimiento(
                    inventario_id=inventario.id,
                    entrada=0,
                    merma=item.cantidad,
                    existencia_final=existencia_final,
                    tipo=TIPO_SALIDA_VENTA,
                    referencia=_referencia_presupuesto(cotizacion.id),
                    usuario_id=current_user["id"]
                ))

            cotizacion.detalles = detalles
        else:
            total_normal = cotizacion.total_normal
            detalles = list(cotizacion.detalles)

        promocion = cond = None
        if cotizacion.promocion_id is not None:
            # la promocion se valido al vender; al modificar solo se vuelve a aplicar
            promocion = await cargar_promocion(db, cotizacion.promocion_id)
            cond = condiciones_por_categoria(promocion)
        total_venta = await _aplicar_descuentos(db, detalles, tipo_cliente.porcentaje_descuento, promocion, cond)
        pago_inicial = cotizacion_update.pago_inicial if cotizacion_update.pago_inicial is not None else cotizacion.pago_inicial
        abonado_result = await db.execute(
            select(func.coalesce(func.sum(Abonos.monto), 0)).where(Abonos.cotizacion_id == cotizacion.id)
        )
        pago_restante = total_venta - pago_inicial - Decimal(abonado_result.scalar_one())
        if pago_restante < 0:
            raise HTTPException(status_code=400, detail="El total de la venta no puede ser menor a lo ya pagado")

        if cotizacion_update.sucursal_id is not None:
            cotizacion.sucursal_id = cotizacion_update.sucursal_id
        if cotizacion_update.usuario_id is not None:
            cotizacion.usuario_id = cotizacion_update.usuario_id
        if cotizacion_update.id_cliente is not None:
            cotizacion.id_cliente = cotizacion_update.id_cliente
        if cotizacion_update.id_paciente is not None:
            cotizacion.id_paciente = cotizacion_update.id_paciente
        if cotizacion_update.tipo_venta is not None:
            cotizacion.tipo_venta = cotizacion_update.tipo_venta
        if cotizacion_update.plazo is not None:
            plazo_result = await db.execute(select(Plazo).where(Plazo.id == cotizacion_update.plazo))
            plazo_obj = plazo_result.scalar_one_or_none()
            if not plazo_obj:
                raise HTTPException(status_code=404, detail="Plazo no encontrado")
            cotizacion.plazo = cotizacion_update.plazo
            cotizacion.vencimiento = _calcular_vencimiento(cotizacion.fecha, plazo_obj.plazo)
        if cotizacion_update.promesa_entrega is not None:
            cotizacion.promesa_entrega = cotizacion_update.promesa_entrega

        cotizacion.pago_inicial = pago_inicial
        cotizacion.pago_restante = pago_restante
        cotizacion.total_normal = total_normal
        cotizacion.total_venta = total_venta

        db.add(cotizacion)
        db.add_all(movimientos)
        await db.commit()

        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id == cotizacion.id)
        )
        return result.scalar_one()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")


@router.delete('/delete/{cotizacion_id}')
async def delete_cotizacion(
    cotizacion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id == cotizacion_id)
        )
        cotizacion = result.scalar_one_or_none()
        if not cotizacion:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")

        abonos_result = await db.execute(select(Abonos.id).where(Abonos.cotizacion_id == cotizacion_id).limit(1))
        if abonos_result.first():
            raise HTTPException(status_code=400, detail="No se puede eliminar una cotizacion que ya tiene abonos registrados")

        # restaurar la existencia de los productos antes de eliminar la cotizacion
        movimientos = []
        for detalle in cotizacion.detalles:
            inv_result = await db.execute(
                select(InventarioSucursal).where(
                    InventarioSucursal.sucursal_id == cotizacion.sucursal_id,
                    InventarioSucursal.producto_id == detalle.producto_id
                )
            )
            inventario = inv_result.scalar_one_or_none()
            if inventario:
                existencia_final = inventario.existencia_actual + detalle.cantidad
                inventario.existencia_actual = existencia_final
                movimientos.append(InventarioMovimiento(
                    inventario_id=inventario.id,
                    entrada=detalle.cantidad,
                    merma=0,
                    existencia_final=existencia_final,
                    tipo=TIPO_ENTRADA_CANCELACION_VENTA,
                    referencia=_referencia_presupuesto(cotizacion.id),
                    usuario_id=current_user["id"]
                ))

        db.add_all(movimientos)
        await db.delete(cotizacion)
        await db.commit()
        return {"message": "Cotizacion eliminada correctamente"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")
