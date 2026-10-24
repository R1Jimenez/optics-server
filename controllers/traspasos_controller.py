from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.traspasos_model import (
    Traspasos, TraspasoDetalle, TraspasoCreate, TraspasoItem, TraspasoOut, TraspasoResumenOut,
    TraspasoDetalleOut, TraspasosPaginaOut,
    ESTATUS_TRASPASO, ESTATUS_NUEVO, ESTATUS_ENVIADO, ESTATUS_RECIBIDO, ESTATUS_CANCELADO
)
from models.inventario_model import (
    InventarioSucursal, InventarioMovimiento,
    TIPO_SALIDA_TRASPASO, TIPO_ENTRADA_TRASPASO, TIPO_ENTRADA_CANCELACION_TRASPASO
)
from models.sucursales_model import Sucursal
from models.producto_model import Productos

router = APIRouter(prefix="/traspasos", tags=["Traspasos"], dependencies=[Depends(get_current_user)])

# Estatus desde los que se permite cada accion
TRANSICIONES = {
    "editar": {ESTATUS_NUEVO},
    "enviar": {ESTATUS_NUEVO},
    "recibir": {ESTATUS_ENVIADO},
    "cancelar": {ESTATUS_NUEVO, ESTATUS_ENVIADO},
}


# ---------- Reglas de negocio (sin acceso a BD) ----------

def consolidar_productos(items: list[TraspasoItem]) -> dict[int, int]:
    """Suma las cantidades de un mismo producto capturado en varios renglones."""
    cantidades: dict[int, int] = {}
    for item in items:
        cantidades[item.producto_id] = cantidades.get(item.producto_id, 0) + item.cantidad
    return cantidades


def validar_sucursales(origen_id: int, destino_id: int) -> None:
    if origen_id == destino_id:
        raise HTTPException(status_code=400, detail="La sucursal de origen y destino deben ser diferentes")


def validar_transicion(estatus_actual: str, accion: str) -> None:
    if estatus_actual not in TRANSICIONES[accion]:
        raise HTTPException(
            status_code=400,
            detail=f"No se puede {accion} un traspaso con estatus '{estatus_actual}'"
        )


def validar_existencias(cantidades: dict[int, int], existencias: dict[int, int], nombres: dict[int, str]) -> None:
    """existencias: producto_id -> existencia en la sucursal de origen (ausente = el producto no esta en esa sucursal)."""
    errores = []
    for producto_id, cantidad in cantidades.items():
        nombre = nombres.get(producto_id, f"Producto #{producto_id}")
        if producto_id not in existencias:
            errores.append(f"{nombre} no esta disponible en la sucursal de origen")
        elif cantidad > existencias[producto_id]:
            errores.append(f"{nombre}: se solicitan {cantidad} y solo hay {existencias[producto_id]} en existencia")
    if errores:
        raise HTTPException(status_code=400, detail="; ".join(errores))


# ---------- Acceso a datos ----------

async def _inventarios(db: AsyncSession, sucursal_id: int, producto_ids, bloquear: bool = False) -> dict[int, InventarioSucursal]:
    if not producto_ids:
        return {}
    query = select(InventarioSucursal).where(
        InventarioSucursal.sucursal_id == sucursal_id,
        InventarioSucursal.producto_id.in_(list(producto_ids))
    )
    if bloquear:
        # FOR UPDATE evita que dos operaciones simultaneas dejen existencias negativas
        query = query.with_for_update()
    result = await db.execute(query)
    return {inv.producto_id: inv for inv in result.scalars().all()}


async def _nombres_productos(db: AsyncSession, producto_ids) -> dict[int, str]:
    if not producto_ids:
        return {}
    result = await db.execute(select(Productos.id, Productos.nombre).where(Productos.id.in_(list(producto_ids))))
    return {pid: nombre for pid, nombre in result.all()}


async def _cargar(db: AsyncSession, traspaso_id: int, bloquear: bool = False) -> Traspasos:
    query = (
        select(Traspasos)
        .options(
            selectinload(Traspasos.origen),
            selectinload(Traspasos.destino),
            selectinload(Traspasos.creador),
            selectinload(Traspasos.modificador),
            selectinload(Traspasos.detalles).selectinload(TraspasoDetalle.producto),
        )
        .where(Traspasos.id == traspaso_id)
        .execution_options(populate_existing=True)
    )
    if bloquear:
        query = query.with_for_update(of=Traspasos)
    traspaso = (await db.execute(query)).scalar_one_or_none()
    if not traspaso:
        raise HTTPException(status_code=404, detail="Traspaso no encontrado")
    return traspaso


async def _validar_sucursales_existen(db: AsyncSession, *sucursal_ids: int) -> None:
    result = await db.execute(select(Sucursal.id).where(Sucursal.id.in_(sucursal_ids)))
    encontradas = set(result.scalars().all())
    faltantes = [str(s) for s in sucursal_ids if s not in encontradas]
    if faltantes:
        raise HTTPException(status_code=404, detail=f"Sucursal no encontrada: {', '.join(faltantes)}")


async def _validar_solicitud(db: AsyncSession, datos: TraspasoCreate) -> dict[int, int]:
    validar_sucursales(datos.sucursal_origen_id, datos.sucursal_destino_id)
    await _validar_sucursales_existen(db, datos.sucursal_origen_id, datos.sucursal_destino_id)
    cantidades = consolidar_productos(datos.productos)
    inventarios = await _inventarios(db, datos.sucursal_origen_id, cantidades.keys())
    validar_existencias(
        cantidades,
        {pid: inv.existencia_actual for pid, inv in inventarios.items()},
        await _nombres_productos(db, cantidades.keys())
    )
    return cantidades


def _resumen(t: Traspasos) -> dict:
    return dict(
        id=t.id,
        origen=t.origen.sucursal if t.origen else "N/A",
        destino=t.destino.sucursal if t.destino else "N/A",
        estatus=t.estatus,
        promesa_entrega=t.promesa_entrega,
        creado_por=t.creador.usuario if t.creador else "N/A",
        fecha_creacion=t.fecha_creacion,
        modificado_por=t.modificador.usuario if t.modificador else "N/A",
        fecha_modificacion=t.fecha_modificacion,
    )


async def _construir_out(db: AsyncSession, t: Traspasos) -> TraspasoOut:
    inventarios = await _inventarios(db, t.sucursal_origen_id, [d.producto_id for d in t.detalles])
    return TraspasoOut(
        **_resumen(t),
        comentarios=t.comentarios,
        sucursal_origen_id=t.sucursal_origen_id,
        sucursal_destino_id=t.sucursal_destino_id,
        detalles=[
            TraspasoDetalleOut(
                producto_id=d.producto_id,
                codigo=d.producto.codigo,
                nombre=d.producto.nombre,
                descripcion=d.producto.descripcion,
                codigo_externo=d.producto.codigo_externo,
                punto_reorden=inventarios[d.producto_id].punto_reorden if d.producto_id in inventarios else 0,
                existencia_origen=inventarios[d.producto_id].existencia_actual if d.producto_id in inventarios else 0,
                cantidad_solicitada=d.cantidad_solicitada,
                cantidad_enviada=d.cantidad_enviada,
                cantidad_recibida=d.cantidad_recibida,
            )
            for d in t.detalles
        ]
    )


def _marcar_modificado(t: Traspasos, usuario_id: int) -> None:
    t.modificado_por = usuario_id
    t.fecha_modificacion = datetime.utcnow()


def _referencia(t: Traspasos) -> str:
    return f"Traspaso {t.id}"


# ---------- Endpoints ----------

@router.get("/estatus", response_model=list[str])
async def get_estatus():
    return ESTATUS_TRASPASO


@router.get("/all", response_model=TraspasosPaginaOut)
async def listar_traspasos(
    estatus: str | None = Query(None),
    origen_id: int | None = Query(None),
    destino_id: int | None = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Traspasos)
        if estatus:
            query = query.where(Traspasos.estatus == estatus)
        if origen_id is not None:
            query = query.where(Traspasos.sucursal_origen_id == origen_id)
        if destino_id is not None:
            query = query.where(Traspasos.sucursal_destino_id == destino_id)

        total = await db.scalar(select(func.count()).select_from(query.subquery()))
        result = await db.execute(
            query.options(
                selectinload(Traspasos.origen),
                selectinload(Traspasos.destino),
                selectinload(Traspasos.creador),
                selectinload(Traspasos.modificador),
            )
            .order_by(Traspasos.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )
        items = [TraspasoResumenOut(**_resumen(t)) for t in result.scalars().all()]
        return TraspasosPaginaOut(total=total, pagina=pagina, por_pagina=por_pagina, items=items)
    except Exception as e:
        print(f"Error al listar traspasos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/{traspaso_id}", response_model=TraspasoOut)
async def get_traspaso(traspaso_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await _construir_out(db, await _cargar(db, traspaso_id))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener traspaso: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/create", response_model=TraspasoOut)
async def crear_traspaso(
    datos: TraspasoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        cantidades = await _validar_solicitud(db, datos)
        traspaso = Traspasos(
            comentarios=datos.comentarios,
            sucursal_origen_id=datos.sucursal_origen_id,
            sucursal_destino_id=datos.sucursal_destino_id,
            estatus=ESTATUS_NUEVO,
            promesa_entrega=datos.promesa_entrega,
            creado_por=current_user["id"],
            modificado_por=current_user["id"],
            detalles=[
                TraspasoDetalle(producto_id=pid, cantidad_solicitada=cantidad)
                for pid, cantidad in cantidades.items()
            ]
        )
        db.add(traspaso)
        await db.commit()
        return await _construir_out(db, await _cargar(db, traspaso.id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear traspaso: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/update/{traspaso_id}", response_model=TraspasoOut)
async def actualizar_traspaso(
    traspaso_id: int,
    datos: TraspasoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        traspaso = await _cargar(db, traspaso_id, bloquear=True)
        validar_transicion(traspaso.estatus, "editar")
        cantidades = await _validar_solicitud(db, datos)

        traspaso.comentarios = datos.comentarios
        traspaso.sucursal_origen_id = datos.sucursal_origen_id
        traspaso.sucursal_destino_id = datos.sucursal_destino_id
        traspaso.promesa_entrega = datos.promesa_entrega
        traspaso.detalles = [
            TraspasoDetalle(producto_id=pid, cantidad_solicitada=cantidad)
            for pid, cantidad in cantidades.items()
        ]
        _marcar_modificado(traspaso, current_user["id"])

        await db.commit()
        return await _construir_out(db, await _cargar(db, traspaso_id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar traspaso: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/{traspaso_id}/enviar", response_model=TraspasoOut)
async def enviar_traspaso(
    traspaso_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        traspaso = await _cargar(db, traspaso_id, bloquear=True)
        validar_transicion(traspaso.estatus, "enviar")

        cantidades = {d.producto_id: d.cantidad_solicitada for d in traspaso.detalles}
        inventarios = await _inventarios(db, traspaso.sucursal_origen_id, cantidades.keys(), bloquear=True)
        # la existencia pudo cambiar desde que se capturo el traspaso
        validar_existencias(
            cantidades,
            {pid: inv.existencia_actual for pid, inv in inventarios.items()},
            {d.producto_id: d.producto.nombre for d in traspaso.detalles}
        )

        for detalle in traspaso.detalles:
            inventario = inventarios[detalle.producto_id]
            inventario.existencia_actual -= detalle.cantidad_solicitada
            detalle.cantidad_enviada = detalle.cantidad_solicitada
            db.add(InventarioMovimiento(
                inventario_id=inventario.id,
                entrada=0,
                merma=detalle.cantidad_solicitada,
                existencia_final=inventario.existencia_actual,
                tipo=TIPO_SALIDA_TRASPASO,
                referencia=_referencia(traspaso),
                usuario_id=current_user["id"]
            ))

        traspaso.estatus = ESTATUS_ENVIADO
        _marcar_modificado(traspaso, current_user["id"])
        await db.commit()
        return await _construir_out(db, await _cargar(db, traspaso_id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al enviar traspaso: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/{traspaso_id}/recibir", response_model=TraspasoOut)
async def recibir_traspaso(
    traspaso_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        traspaso = await _cargar(db, traspaso_id, bloquear=True)
        validar_transicion(traspaso.estatus, "recibir")

        producto_ids = [d.producto_id for d in traspaso.detalles]
        inventarios = await _inventarios(db, traspaso.sucursal_destino_id, producto_ids, bloquear=True)

        for detalle in traspaso.detalles:
            inventario = inventarios.get(detalle.producto_id)
            if inventario is None:
                # el producto aun no se manejaba en la sucursal destino
                inventario = InventarioSucursal(
                    sucursal_id=traspaso.sucursal_destino_id,
                    producto_id=detalle.producto_id,
                    existencia_actual=0,
                    punto_reorden=0
                )
                db.add(inventario)
                await db.flush()

            recibida = detalle.cantidad_enviada or 0
            inventario.existencia_actual += recibida
            detalle.cantidad_recibida = recibida
            db.add(InventarioMovimiento(
                inventario_id=inventario.id,
                entrada=recibida,
                merma=0,
                existencia_final=inventario.existencia_actual,
                tipo=TIPO_ENTRADA_TRASPASO,
                referencia=_referencia(traspaso),
                usuario_id=current_user["id"]
            ))

        traspaso.estatus = ESTATUS_RECIBIDO
        _marcar_modificado(traspaso, current_user["id"])
        await db.commit()
        return await _construir_out(db, await _cargar(db, traspaso_id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al recibir traspaso: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/{traspaso_id}/cancelar", response_model=TraspasoOut)
async def cancelar_traspaso(
    traspaso_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        traspaso = await _cargar(db, traspaso_id, bloquear=True)
        validar_transicion(traspaso.estatus, "cancelar")

        if traspaso.estatus == ESTATUS_ENVIADO:
            # la mercancia ya habia salido del origen: se regresa
            inventarios = await _inventarios(
                db, traspaso.sucursal_origen_id, [d.producto_id for d in traspaso.detalles], bloquear=True
            )
            for detalle in traspaso.detalles:
                inventario = inventarios[detalle.producto_id]
                devuelta = detalle.cantidad_enviada or 0
                inventario.existencia_actual += devuelta
                db.add(InventarioMovimiento(
                    inventario_id=inventario.id,
                    entrada=devuelta,
                    merma=0,
                    existencia_final=inventario.existencia_actual,
                    tipo=TIPO_ENTRADA_CANCELACION_TRASPASO,
                    referencia=_referencia(traspaso),
                    usuario_id=current_user["id"]
                ))

        traspaso.estatus = ESTATUS_CANCELADO
        _marcar_modificado(traspaso, current_user["id"])
        await db.commit()
        return await _construir_out(db, await _cargar(db, traspaso_id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al cancelar traspaso: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
