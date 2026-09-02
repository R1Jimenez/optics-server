from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from models.precios_sucursal_model import PreciosSucursal, PrecioSucursalCreate, PrecioSucursalUpdate, PrecioSucursalOut
from models.producto_model import Productos
from models.sucursales_model import Sucursal
from middleware.auth import get_current_user

router = APIRouter(prefix="/precioporproducto", tags=["PrecioSucursal"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=PrecioSucursalOut)
async def create_precio_sucursal(precsuc: PrecioSucursalCreate, db: AsyncSession = Depends(get_db)):
    try:
        producto_query = select(Productos).where(Productos.id == precsuc.producto)
        producto_result = await db.execute(producto_query)
        if not producto_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        sucursal_query = select(Sucursal).where(Sucursal.id == precsuc.sucursal)
        sucursal_result = await db.execute(sucursal_query)
        if not sucursal_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")

        query = select(PreciosSucursal).where(
            PreciosSucursal.sucursal == precsuc.sucursal,
            PreciosSucursal.producto == precsuc.producto
        )
        result = await db.execute(query)
        existence = result.scalar_one_or_none()

        if existence:
            raise HTTPException(
                status_code=400,
                detail="Ya existe un precio establecido para este producto"
            )

        if precsuc.precio <= precsuc.costo:
            raise HTTPException(
                status_code=400,
                detail="El precio no puede ser menor o igual al costo"
            )

        nuevo_precio = PreciosSucursal(
            sucursal=precsuc.sucursal,
            producto=precsuc.producto,
            costo=precsuc.costo,
            precio=precsuc.precio
        )

        db.add(nuevo_precio)
        await db.commit()
        await db.refresh(nuevo_precio)

        return nuevo_precio

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear precio de sucursal: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/{producto_id}", response_model=list[PrecioSucursalOut])
async def get_precios_producto(
    producto_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        prodquery = select(PreciosSucursal).where(PreciosSucursal.producto == producto_id)
        result = await db.execute(prodquery)
        productoresult = result.scalars().all()

        if not productoresult:
            raise HTTPException(status_code=400, detail="No se encontro ningun precio establecido para este producto")

        return productoresult

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en el servidor {e}")

@router.post("/update/{precio_id}", response_model=PrecioSucursalOut)
async def update_precio_sucursal(
    precio_id: int,
    datos: PrecioSucursalUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(PreciosSucursal).where(PreciosSucursal.id == precio_id)
        result = await db.execute(query)
        precio = result.scalar_one_or_none()

        if not precio:
            raise HTTPException(status_code=404, detail="No se encontro este registro de precio")

        nueva_sucursal = datos.sucursal if datos.sucursal is not None else precio.sucursal
        nuevo_producto = datos.producto if datos.producto is not None else precio.producto

        if nueva_sucursal != precio.sucursal or nuevo_producto != precio.producto:
            dup_query = select(PreciosSucursal).where(
                PreciosSucursal.sucursal == nueva_sucursal,
                PreciosSucursal.producto == nuevo_producto,
                PreciosSucursal.id != precio_id
            )
            dup_result = await db.execute(dup_query)
            duplicado = dup_result.scalar_one_or_none()

            if duplicado:
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe un precio establecido para este producto en esta sucursal"
                )

        nuevo_costo = datos.costo if datos.costo is not None else precio.costo
        nuevo_precio = datos.precio if datos.precio is not None else precio.precio

        if nuevo_costo is not None and nuevo_precio <= nuevo_costo:
            raise HTTPException(
                status_code=400,
                detail="El precio no puede ser menor o igual al costo"
            )

        datos_actualizados = datos.model_dump(exclude_unset=True)
        for campo, valor in datos_actualizados.items():
            setattr(precio, campo, valor)

        await db.commit()
        await db.refresh(precio)

        return precio

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar precio de sucursal: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.delete("/delete/{precprod_id}")
async def delete_precio_producto(precprod_id: int, db: AsyncSession = Depends(get_db)):
    try:
        precprod = select(PreciosSucursal).where(PreciosSucursal.id == precprod_id)
        result = await db.execute(precprod)
        precprodresult = result.scalar_one_or_none()

        if not precprodresult:
            raise HTTPException(status_code=404, detail="No se encontro este producto")

        await db.delete(precprodresult)
        await db.commit()
        return {"detail": "Precio por este producto eliminado exitosamente"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))