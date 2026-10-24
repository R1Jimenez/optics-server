from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, or_
from database.database import get_db
from models.inventario_model import (
    InventarioSucursal, InventarioSucursalCreate, InventarioSucursalUpdate, InventarioSucursalOut,
    InventarioMovimiento, InventarioMovimientoCreate, InventarioMovimientoOut, ProductoInventarioOut,
    MovimientoDetalleOut, MovimientosPaginaOut, ProductoBusquedaOut,
    TIPOS_MOVIMIENTO, TIPOS_MOVIMIENTO_MANUAL, TIPO_ENTRADA_AJUSTE, TIPO_SALIDA_AJUSTE, TIPO_AJUSTE
)
from models.producto_model import Productos
from models.sucursales_model import Sucursal
from models.users_model import User
from middleware.auth import get_current_user

router = APIRouter(prefix="/inventario", tags=["Inventario"], dependencies=[Depends(get_current_user)])


def _tipo_ajuste(entrada: int, merma: int) -> str:
    if entrada > 0 and merma > 0:
        return TIPO_AJUSTE
    return TIPO_ENTRADA_AJUSTE if entrada > 0 else TIPO_SALIDA_AJUSTE


def _a_utc_naive(fecha: datetime) -> datetime:
    # las fechas se guardan en UTC sin zona horaria
    if fecha.tzinfo is None:
        return fecha
    return fecha.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("/tipos-movimiento", response_model=list[str])
async def get_tipos_movimiento():
    # "Entrada"/"Salida" agrupan los movimientos registrados antes de clasificarlos por tipo
    return TIPOS_MOVIMIENTO + ["Entrada", "Salida"]


@router.get("/movimientos", response_model=MovimientosPaginaOut)
async def listar_movimientos(
    producto: str | None = Query(None),
    codigo: str | None = Query(None),
    sucursal_id: int | None = Query(None),
    tipo: str | None = Query(None),
    referencia: str | None = Query(None),
    desde: datetime | None = Query(None),
    hasta: datetime | None = Query(None),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    try:
        # movimientos anteriores a la columna tipo solo se distinguen por entrada/salida
        tipo_expr = func.coalesce(
            InventarioMovimiento.tipo,
            case((InventarioMovimiento.entrada > 0, "Entrada"), else_="Salida")
        )

        query = (
            select(InventarioMovimiento, InventarioSucursal, Productos, Sucursal, User, tipo_expr.label("tipo_mov"))
            .join(InventarioSucursal, InventarioSucursal.id == InventarioMovimiento.inventario_id)
            .join(Productos, Productos.id == InventarioSucursal.producto_id)
            .join(Sucursal, Sucursal.id == InventarioSucursal.sucursal_id)
            .outerjoin(User, User.id == InventarioMovimiento.usuario_id)
        )

        if producto:
            query = query.where(Productos.nombre.ilike(f"%{producto}%"))
        if codigo:
            query = query.where(or_(
                Productos.codigo.ilike(f"%{codigo}%"),
                Productos.codigo_externo.ilike(f"%{codigo}%")
            ))
        if sucursal_id is not None:
            query = query.where(InventarioSucursal.sucursal_id == sucursal_id)
        if tipo:
            query = query.where(tipo_expr == tipo)
        if referencia:
            query = query.where(InventarioMovimiento.referencia.ilike(f"%{referencia}%"))
        if desde is not None:
            query = query.where(InventarioMovimiento.fecha >= _a_utc_naive(desde))
        if hasta is not None:
            query = query.where(InventarioMovimiento.fecha < _a_utc_naive(hasta))

        total = await db.scalar(select(func.count()).select_from(query.subquery()))

        result = await db.execute(
            query.order_by(InventarioMovimiento.fecha.desc(), InventarioMovimiento.id.desc())
            .offset((pagina - 1) * por_pagina)
            .limit(por_pagina)
        )

        items = [
            MovimientoDetalleOut(
                id=mov.id,
                fecha=mov.fecha,
                sucursal_id=sucursal.id,
                sucursal=sucursal.sucursal,
                producto_id=prod.id,
                codigo=prod.codigo,
                producto=prod.nombre,
                tipo=tipo_mov,
                referencia=mov.referencia,
                usuario=f"{usuario.nombres} {usuario.apellidos}" if usuario else None,
                existencia_anterior=mov.existencia_final - mov.entrada + mov.merma,
                entradas=mov.entrada,
                salidas=mov.merma,
                saldo=mov.existencia_final
            )
            for mov, _inv, prod, sucursal, usuario, tipo_mov in result.all()
        ]

        return MovimientosPaginaOut(total=total, pagina=pagina, por_pagina=por_pagina, items=items)
    except Exception as e:
        print(f"Error al listar movimientos de inventario: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.post("/create", response_model=InventarioSucursalOut)
async def create_inventario(inv: InventarioSucursalCreate, db: AsyncSession = Depends(get_db)):
    try:
        producto_result = await db.execute(select(Productos).where(Productos.id == inv.producto_id))
        if not producto_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        sucursal_result = await db.execute(select(Sucursal).where(Sucursal.id == inv.sucursal_id))
        if not sucursal_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")

        existing = await db.execute(select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == inv.sucursal_id,
            InventarioSucursal.producto_id == inv.producto_id
        ))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Ya existe un inventario para este producto en esta sucursal")

        nuevo_inventario = InventarioSucursal(**inv.model_dump())
        db.add(nuevo_inventario)
        await db.commit()
        await db.refresh(nuevo_inventario)

        return nuevo_inventario

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear inventario: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/sucursal/{sucursal_id}/productos", response_model=list[ProductoInventarioOut])
async def get_productos_por_sucursal(
    sucursal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        sucursal_result = await db.execute(select(Sucursal).where(Sucursal.id == sucursal_id))
        if not sucursal_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")

        query = select(InventarioSucursal, Productos).join(
            Productos, Productos.id == InventarioSucursal.producto_id
        ).where(InventarioSucursal.sucursal_id == sucursal_id)

        result = await db.execute(query)
        rows = result.all()

        return [
            ProductoInventarioOut(
                producto_id=producto.id,
                codigo=producto.codigo,
                nombre=producto.nombre,
                descripcion=producto.descripcion,
                existencia_actual=inventario.existencia_actual,
                punto_reorden=inventario.punto_reorden
            )
            for inventario, producto in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en el servidor {e}")

# Debe declararse antes de /sucursal/{sucursal_id}/{producto_id} para que "buscar" no se interprete como producto_id
@router.get("/sucursal/{sucursal_id}/buscar", response_model=list[ProductoBusquedaOut])
async def buscar_productos_sucursal(
    sucursal_id: int,
    q: str = Query(..., min_length=1),
    limite: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    try:
        patron = f"%{q.strip()}%"
        result = await db.execute(
            select(InventarioSucursal, Productos)
            .join(Productos, Productos.id == InventarioSucursal.producto_id)
            .where(
                InventarioSucursal.sucursal_id == sucursal_id,
                or_(
                    Productos.codigo.ilike(patron),
                    Productos.nombre.ilike(patron),
                    Productos.codigo_externo.ilike(patron)
                )
            )
            .order_by(Productos.nombre)
            .limit(limite)
        )
        return [
            ProductoBusquedaOut(
                producto_id=producto.id,
                codigo=producto.codigo,
                nombre=producto.nombre,
                descripcion=producto.descripcion,
                codigo_externo=producto.codigo_externo,
                existencia_actual=inventario.existencia_actual,
                punto_reorden=inventario.punto_reorden
            )
            for inventario, producto in result.all()
        ]
    except Exception as e:
        print(f"Error al buscar productos en sucursal: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/sucursal/{sucursal_id}/{producto_id}", response_model=InventarioSucursalOut)
async def get_inventario_sucursal(
    sucursal_id: int,
    producto_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        query = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == sucursal_id,
            InventarioSucursal.producto_id == producto_id
        )
        result = await db.execute(query)
        inventario = result.scalar_one_or_none()

        if not inventario:
            raise HTTPException(status_code=404, detail="No se encontro inventario para este producto en esta sucursal")

        return inventario

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en el servidor {e}")

@router.post("/update/{inventario_id}", response_model=InventarioSucursalOut)
async def update_inventario(
    inventario_id: int,
    datos: InventarioSucursalUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(InventarioSucursal).where(InventarioSucursal.id == inventario_id)
        result = await db.execute(query)
        inventario = result.scalar_one_or_none()

        if not inventario:
            raise HTTPException(status_code=404, detail="No se encontro este registro de inventario")

        datos_actualizados = datos.model_dump(exclude_unset=True)
        for campo, valor in datos_actualizados.items():
            setattr(inventario, campo, valor)

        await db.commit()
        await db.refresh(inventario)

        return inventario

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno en el servidor {e}")

@router.post("/movimiento", response_model=InventarioMovimientoOut)
async def registrar_movimiento(
    mov: InventarioMovimientoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        if mov.tipo is not None and mov.tipo not in TIPOS_MOVIMIENTO_MANUAL:
            raise HTTPException(status_code=400, detail=f"Tipo de movimiento no valido: {mov.tipo}")

        query = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == mov.sucursal_id,
            InventarioSucursal.producto_id == mov.producto_id
        )
        result = await db.execute(query)
        inventario = result.scalar_one_or_none()

        if not inventario:
            raise HTTPException(status_code=404, detail="No se encontro inventario para este producto en esta sucursal")

        existencia_final = inventario.existencia_actual + mov.entrada - mov.merma
        if existencia_final < 0:
            raise HTTPException(status_code=400, detail="La merma no puede ser mayor a la existencia disponible")

        nuevo_movimiento = InventarioMovimiento(
            inventario_id=inventario.id,
            entrada=mov.entrada,
            merma=mov.merma,
            existencia_final=existencia_final,
            tipo=mov.tipo or _tipo_ajuste(mov.entrada, mov.merma),
            referencia=mov.referencia,
            usuario_id=current_user["id"]
        )

        inventario.existencia_actual = existencia_final

        db.add(nuevo_movimiento)
        await db.commit()
        await db.refresh(nuevo_movimiento)

        return nuevo_movimiento

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al registrar movimiento de inventario: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/movimientos/{inventario_id}", response_model=list[InventarioMovimientoOut])
async def get_movimientos(
    inventario_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        query = select(InventarioMovimiento).where(InventarioMovimiento.inventario_id == inventario_id)
        result = await db.execute(query)
        movimientos = result.scalars().all()

        return movimientos

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en el servidor {e}")


