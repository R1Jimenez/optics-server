from fastapi import APIRouter, HTTPException, Query, Depends 
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select, or_, exists, delete
from sqlalchemy.exc import IntegrityError
from database.database import get_db
from middleware.auth import get_current_user
from models.producto_model import Productos, ProductoCreate, ProductoAtributo, ProductOut
from models.atributos_model import Atributo
from models.atributos_valores_model import AtributosValores
from models.inventario_model import InventarioSucursal, ProductoInventarioOut
from models.precios_sucursal_model import PreciosSucursal
from models.cotizacion_model import CotizacionDetalle
from models.sucursales_model import Sucursal

router = APIRouter(prefix="/productos", tags=["Productos"], dependencies=[Depends(get_current_user)])


async def _atributos_por_producto(db: AsyncSession, producto_ids) -> dict[int, dict[int, int]]:
    """producto_id -> {atributo_id: atributovalor_id}, en una sola consulta."""
    ids = list(producto_ids)
    if not ids:
        return {}
    result = await db.execute(
        select(ProductoAtributo.producto_id, ProductoAtributo.atributo_id, ProductoAtributo.atributovalor_id)
        .where(ProductoAtributo.producto_id.in_(ids))
    )
    atributos: dict[int, dict[int, int]] = {}
    for producto_id, atributo_id, valor_id in result.all():
        atributos.setdefault(producto_id, {})[atributo_id] = valor_id
    return atributos


def _producto_out(producto: Productos, atributos_seleccionados: dict[int, int]) -> ProductOut:
    return ProductOut(
        id=producto.id,
        nombre=producto.nombre,
        codigo=producto.codigo,
        codigo_externo=producto.codigo_externo,
        descripcion=producto.descripcion,
        estatus=producto.estatus,
        tipo=producto.tipo,
        genera_orden=producto.genera_orden,
        unidad=producto.unidad,
        tipo_iva=producto.tipo_iva,
        atributos_seleccionados=atributos_seleccionados
    )


async def _armar_codigo(db: AsyncSession, seleccionados: dict[int, int]) -> tuple[str, str, dict[int, int]]:
    """Codigo = claves de cada atributo en orden; sin seleccion se usa la menor clave del atributo.
    Devuelve (codigo, nombre, {atributo_id: valor_id})."""
    atributos = (await db.execute(select(Atributo).order_by(Atributo.id))).scalars().all()
    if not atributos:
        raise HTTPException(status_code=400, detail="No hay atributos definidos")

    valores = (await db.execute(
        select(AtributosValores)
        .where(AtributosValores.atributo_id.in_([a.id for a in atributos]))
        .order_by(AtributosValores.clave)
    )).scalars().all()
    por_id = {v.id: v for v in valores}
    predeterminado: dict[int, AtributosValores] = {}
    for v in valores:
        predeterminado.setdefault(v.atributo_id, v)

    partes_codigo, partes_nombre, guardados = [], [], {}
    for atributo in atributos:
        valor_id = seleccionados.get(atributo.id)
        if valor_id is not None:
            valor = por_id.get(valor_id)
            if not valor or valor.atributo_id != atributo.id:
                raise HTTPException(
                    status_code=404,
                    detail=f"Valor con id {valor_id} no encontrado para atributo {atributo.atributo}"
                )
            partes_codigo.append(valor.clave)
            if valor.descripcion:
                partes_nombre.append(valor.descripcion)
            guardados[atributo.id] = valor_id
        elif atributo.id in predeterminado:
            partes_codigo.append(predeterminado[atributo.id].clave)
            guardados[atributo.id] = predeterminado[atributo.id].id
        else:
            partes_codigo.append("0" * atributo.longitud)

    return "".join(partes_codigo), " ".join(partes_nombre) if partes_nombre else "Sin nombre", guardados

@router.post("/create", response_model=ProductOut)
async def create_product(producto: ProductoCreate, db: AsyncSession = Depends(get_db)):
    try:
        codigoexterno = select(Productos).where(Productos.codigo_externo == producto.codigo_externo)
        codigexterno_result = await db.execute(codigoexterno)
        codigo_externo = codigexterno_result.scalar_one_or_none()

        if codigo_externo:
            raise HTTPException(status_code=400, detail="Ya existe un producto con este codigo externo")

        codigo_final, nombre_final, atributos_guardados = await _armar_codigo(db, producto.atributos_seleccionados)

        existing_query = select(Productos).where(Productos.codigo == codigo_final)
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un producto con el codigo {codigo_final}"
            )

        new_producto = Productos(
            nombre = nombre_final,
            codigo = codigo_final,
            codigo_externo = producto.codigo_externo,
            descripcion = producto.descripcion,
            estatus = producto.estatus,
            tipo = producto.tipo,
            genera_orden = producto.genera_orden,
            unidad = producto.unidad,
            tipo_iva = producto.tipo_iva
        )
        db.add(new_producto)
        await db.flush()

        for atributo_id, valor_id in atributos_guardados.items():
            prod_atrib = ProductoAtributo(
                producto_id = new_producto.id,
                atributo_id = atributo_id,
                atributovalor_id = valor_id
            )
            db.add(prod_atrib)

        await db.commit()
        await db.refresh(new_producto)

        return ProductOut(
            id = new_producto.id,
            nombre = new_producto.nombre,
            codigo = new_producto.codigo,
            codigo_externo = new_producto.codigo_externo,
            descripcion = new_producto.descripcion,
            estatus = new_producto.estatus,
            tipo = new_producto.tipo,
            genera_orden = new_producto.genera_orden,
            unidad = new_producto.unidad,
            tipo_iva = new_producto.tipo_iva,
            atributos_seleccionados = atributos_guardados
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear producto: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/all", response_model=list[ProductOut])
async def get_all_productos(db: AsyncSession = Depends(get_db)):
    try:
        query = select(Productos)
        result = await db.execute(query)
        productos = result.scalars().all()

        atributos = await _atributos_por_producto(db, (p.id for p in productos))
        return [_producto_out(p, atributos.get(p.id, {})) for p in productos]

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener productos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/filtroproductos", response_model=list[ProductOut])
async def get_productos_filtrados(
    codigo: Optional[str] = Query(None),
    nombre: Optional[str] = Query(None),
    estatus: Optional[int] = Query(None),
    codigo_externo: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Productos)

        if codigo:
            query = query.where(Productos.codigo == codigo)
        if nombre:
            query = query.where(Productos.nombre.ilike(f"%{nombre}%"))
        if estatus:
            query = query.where(Productos.estatus == estatus)
        if codigo_externo:
            query = query.where(Productos.codigo_externo == codigo_externo)

        result = await db.execute(query)
        productos = result.scalars().all()

        if not productos:
            raise HTTPException(status_code=404, detail="No se encontraron productos con estas caracteristicas")

        atributos = await _atributos_por_producto(db, (p.id for p in productos))
        return [_producto_out(p, atributos.get(p.id, {})) for p in productos]

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener productos: {e}")
        raise HTTPException(status_code=500, detail="Error interno en el servidor")

class ProductoBusquedaGeneralOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    codigo_externo: str


@router.get("/buscar", response_model=list[ProductoBusquedaGeneralOut])
async def buscar_productos(
    q: str = Query(..., min_length=1),
    limite: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Busqueda en todo el catalogo por codigo, nombre o codigo externo."""
    try:
        patron = f"%{q.strip()}%"
        result = await db.execute(
            select(Productos)
            .where(or_(
                Productos.codigo.ilike(patron),
                Productos.nombre.ilike(patron),
                Productos.codigo_externo.ilike(patron)
            ))
            .order_by(Productos.nombre)
            .limit(limite)
        )
        return [
            ProductoBusquedaGeneralOut(id=p.id, codigo=p.codigo, nombre=p.nombre, codigo_externo=p.codigo_externo)
            for p in result.scalars().all()
        ]
    except Exception as e:
        print(f"Error al buscar productos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/sucursal/{sucursal_id}", response_model=list[ProductoInventarioOut])
async def get_productos_por_sucursal(sucursal_id: int, db: AsyncSession = Depends(get_db)):
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
        print(f"Error al obtener productos por sucursal: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.get("/{producto_id}", response_model=ProductOut)
async def get_producto(producto_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Productos).where(Productos.id == producto_id)
        result = await db.execute(query)
        producto = result.scalar_one_or_none()

        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        atribs_query = select(ProductoAtributo).where(
            ProductoAtributo.producto_id == producto_id
        )
        atribs_result = await db.execute(atribs_query)
        atribs = atribs_result.scalars().all()

        atributos_seleccionados = {
            pa.atributo_id: pa.atributovalor_id for pa in atribs
        }

        return ProductOut(
            id = producto.id,
            nombre = producto.nombre,
            codigo = producto.codigo,
            codigo_externo = producto.codigo_externo,
            descripcion = producto.descripcion,
            estatus = producto.estatus,
            tipo = producto.tipo,
            genera_orden = producto.genera_orden,
            unidad = producto.unidad,
            tipo_iva = producto.tipo_iva,
            atributos_seleccionados = atributos_seleccionados
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener producto: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.post("/update/{producto_id}", response_model=ProductOut)
async def update_producto(producto_id: int, producto: ProductoCreate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Productos).where(Productos.id == producto_id)
        result = await db.execute(query)
        producto_actual = result.scalar_one_or_none()

        if not producto_actual:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        codigo_final, nombre_final, atributos_guardados = await _armar_codigo(db, producto.atributos_seleccionados)

        existing_query = select(Productos).where(
            Productos.codigo == codigo_final,
            Productos.id != producto_id
        )
        existing_result = await db.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe otro producto con el código {codigo_final}"
            )

        producto_actual.nombre = nombre_final
        producto_actual.codigo = codigo_final
        producto_actual.codigo_externo = producto.codigo_externo
        producto_actual.descripcion = producto.descripcion
        producto_actual.estatus = producto.estatus
        producto_actual.tipo = producto.tipo
        producto_actual.genera_orden = producto.genera_orden
        producto_actual.unidad = producto.unidad
        producto_actual.tipo_iva = producto.tipo_iva

        atribs_del_query = select(ProductoAtributo).where(
            ProductoAtributo.producto_id == producto_id
        )
        atribs_del_result = await db.execute(atribs_del_query)
        atribs_existentes = atribs_del_result.scalars().all()

        for atrib in atribs_existentes:
            await db.delete(atrib)

        await db.flush()

        for atributo_id, valor_id in atributos_guardados.items():
            prod_atrib = ProductoAtributo(
                producto_id = producto_id,
                atributo_id = atributo_id,
                atributovalor_id = valor_id
            )
            db.add(prod_atrib)

        await db.commit()
        await db.refresh(producto_actual)

        return ProductOut(
            id = producto_actual.id,
            nombre = producto_actual.nombre,
            codigo = producto_actual.codigo,
            codigo_externo = producto_actual.codigo_externo,
            descripcion = producto_actual.descripcion,
            estatus = producto_actual.estatus,
            tipo = producto_actual.tipo,
            genera_orden = producto_actual.genera_orden,
            unidad = producto_actual.unidad,
            tipo_iva = producto_actual.tipo_iva,
            atributos_seleccionados = atributos_guardados
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar producto: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@router.delete("/delete/{producto_id}")
async def delete_producto(producto_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Productos).where(Productos.id == producto_id)
        result = await db.execute(query)
        producto = result.scalar_one_or_none()

        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # inventario y precios no tienen llave foranea: se valida aqui para no dejar registros huerfanos
        en_uso = await db.scalar(select(
            exists().where(InventarioSucursal.producto_id == producto_id)
            | exists().where(PreciosSucursal.producto == producto_id)
            | exists().where(CotizacionDetalle.producto_id == producto_id)
        ))
        if en_uso:
            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar el producto porque tiene inventario, precios o ventas registradas"
            )

        await db.execute(delete(ProductoAtributo).where(ProductoAtributo.producto_id == producto_id))
        await db.delete(producto)
        await db.commit()
        return {"detail": "Producto eliminado exitosamente"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar el producto porque tiene inventario, precios o ventas registradas"
        )
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar producto: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")