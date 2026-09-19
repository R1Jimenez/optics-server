from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.inventario_model import (
    InventarioSucursal, InventarioSucursalCreate, InventarioSucursalUpdate, InventarioSucursalOut,
    InventarioMovimiento, InventarioMovimientoCreate, InventarioMovimientoOut, ProductoInventarioOut
)
from models.producto_model import Productos
from models.sucursales_model import Sucursal
from middleware.auth import get_current_user

router = APIRouter(prefix="/inventario", tags=["Inventario"], dependencies=[Depends(get_current_user)])

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
async def registrar_movimiento(mov: InventarioMovimientoCreate, db: AsyncSession = Depends(get_db)):
    try:
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
            existencia_final=existencia_final
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


