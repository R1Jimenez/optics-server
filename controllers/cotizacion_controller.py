from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.cotizacion_model import Cotizaciones, CotizacionDetalle, CotizacionCreate, CotizacionUpdate, CotizacionOut
from models.inventario_model import InventarioSucursal, InventarioMovimiento
from models.precios_sucursal_model import PreciosSucursal
from models.clientes_model import Cliente
from models.tipo_cliente_model import Tipo_Cliente
from models.ordenes_trabajo_model import OrdenesTrabajo

router = APIRouter(prefix="/cotizacion", tags=["Cotizaciones"], dependencies=[Depends(get_current_user)])


@router.post('/create', response_model=CotizacionOut)
async def create_cotizacion(cotizacion: CotizacionCreate, db: AsyncSession = Depends(get_db)):
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
                existencia_final=existencia_final
            ))

        descuento = total_normal * Decimal(tipo_cliente.porcentaje_descuento) / Decimal("100")
        total_venta = total_normal - descuento
        pago_restante = total_venta - cotizacion.pago_inicial

        nueva_cotizacion = Cotizaciones(
            sucursal_id=cotizacion.sucursal_id,
            usuario_id=cotizacion.usuario_id,
            id_cliente=cotizacion.id_cliente,
            id_paciente=cotizacion.id_paciente,
            tipo_venta=cotizacion.tipo_venta,
            plazo=cotizacion.plazo,
            pago_inicial=cotizacion.pago_inicial,
            pago_restante=pago_restante,
            promesa_entrega=cotizacion.promesa_entrega,
            total_normal=total_normal,
            total_venta=total_venta,
            detalles=detalles
        )

        db.add(nueva_cotizacion)
        db.add_all(movimientos)
        await db.flush()

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
async def update_cotizacion(cotizacion_id: int, cotizacion_update: CotizacionUpdate, db: AsyncSession = Depends(get_db)):
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
                        existencia_final=existencia_final
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
                    existencia_final=existencia_final
                ))

            cotizacion.detalles = detalles
        else:
            total_normal = cotizacion.total_normal

        descuento = total_normal * Decimal(tipo_cliente.porcentaje_descuento) / Decimal("100")
        total_venta = total_normal - descuento
        pago_inicial = cotizacion_update.pago_inicial if cotizacion_update.pago_inicial is not None else cotizacion.pago_inicial
        pago_restante = total_venta - pago_inicial

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
            cotizacion.plazo = cotizacion_update.plazo
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
async def delete_cotizacion(cotizacion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(Cotizaciones)
            .options(selectinload(Cotizaciones.detalles))
            .where(Cotizaciones.id == cotizacion_id)
        )
        cotizacion = result.scalar_one_or_none()
        if not cotizacion:
            raise HTTPException(status_code=404, detail="Cotizacion no encontrada")

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
                    existencia_final=existencia_final
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
