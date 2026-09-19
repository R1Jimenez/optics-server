from fastapi import APIRouter, HTTPException, Query, Depends 
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.producto_model import Productos, ProductoCreate, ProductoAtributo, ProductOut
from models.atributos_model import Atributo
from models.atributos_valores_model import AtributosValores
from models.inventario_model import InventarioSucursal, ProductoInventarioOut
from models.sucursales_model import Sucursal

router = APIRouter(prefix="/productos", tags=["Productos"], dependencies=[Depends(get_current_user)])

@router.post("/create", response_model=ProductOut)
async def create_product(producto: ProductoCreate, db: AsyncSession = Depends(get_db)):
    try:
        atributos_query = select(Atributo).order_by(Atributo.id)
        atributos_result = await db.execute(atributos_query)
        atributos = atributos_result.scalars().all()

        if not atributos:
            raise HTTPException(status_code=400, detail="No hay atributos definidos")

        codigoexterno = select(Productos).where(Productos.codigo_externo == producto.codigo_externo)
        codigexterno_result = await db.execute(codigoexterno)
        codigo_externo = codigexterno_result.scalar_one_or_none()

        if codigo_externo:
            raise HTTPException(status_code=400, detail="Ya existe un producto con este codigo externo")

        partes_codigo = []
        partes_nombre = []
        atributos_guardados = {}

        for atributo in atributos:
            valor_id = producto.atributos_seleccionados.get(atributo.id)
            print(f"Atributo id={atributo.id} nombre={atributo.atributo} → valor_id={valor_id}")

            if valor_id is not None:
                valor_query = select(AtributosValores).where(AtributosValores.id == valor_id)
                valor_result = await db.execute(valor_query)
                valor = valor_result.scalar_one_or_none()

                if not valor:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Valor con id {valor_id} no encontrado para atributo {atributo.atributo}"
                    )

                partes_codigo.append(valor.clave)
                if valor.descripcion:
                    partes_nombre.append(valor.descripcion)
                atributos_guardados[atributo.id] = valor_id

            else:
                default_query = select(AtributosValores).where(
                    AtributosValores.atributo_id == atributo.id
                ).order_by(AtributosValores.clave)
                default_result = await db.execute(default_query)
                default_valor = default_result.scalars().first()

                if default_valor:
                    partes_codigo.append(default_valor.clave)
                    atributos_guardados[atributo.id] = default_valor.id
                else:
                    partes_codigo.append("0" * atributo.longitud)

        codigo_final = "".join(partes_codigo)
        nombre_final = " ".join(partes_nombre) if partes_nombre else "Sin nombre"

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

        productos_out = []
        for producto in productos:
            atribs_query = select(ProductoAtributo).where(
                ProductoAtributo.producto_id == producto.id
            )
            atribs_result = await db.execute(atribs_query)
            atribs = atribs_result.scalars().all()

            atributos_seleccionados = {
                pa.atributo_id: pa.atributovalor_id for pa in atribs
            }

            productos_out.append(ProductOut(
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
            ))

        return productos_out

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

        response = []
        for producto in productos:
            atribs_query = select(ProductoAtributo).where(
                ProductoAtributo.producto_id == producto.id
            )

            atribs_result = await db.execute(atribs_query)
            atribs = atribs_result.scalars().all()

            atributos_seleccionados = {
                pa.atributo_id: pa.atributovalor_id for pa in atribs
            }

            response.append(ProductOut(
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
            ))

        return response

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener productos: {e}")
        raise HTTPException(status_code=500, detail="Error interno en el servidor")

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

        atributos_query = select(Atributo).order_by(Atributo.id)
        atributos_result = await db.execute(atributos_query)
        atributos = atributos_result.scalars().all()

        partes_codigo = []
        partes_nombre = []
        atributos_guardados = {}

        for atributo in atributos:
            valor_id = producto.atributos_seleccionados.get(atributo.id)

            if valor_id is not None:
                valor_query = select(AtributosValores).where(AtributosValores.id == valor_id)
                valor_result = await db.execute(valor_query)
                valor = valor_result.scalar_one_or_none()

                if not valor:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Valor con id {valor_id} no encontrado para atributo {atributo.atributo}"
                    )

                partes_codigo.append(valor.clave)
                if valor.descripcion:
                    partes_nombre.append(valor.descripcion)
                atributos_guardados[atributo.id] = valor_id

            else:
                default_query = select(AtributosValores).where(
                    AtributosValores.atributo_id == atributo.id
                ).order_by(AtributosValores.clave)
                default_result = await db.execute(default_query)
                default_valor = default_result.scalars().first()

                if default_valor:
                    partes_codigo.append(default_valor.clave)
                    atributos_guardados[atributo.id] = default_valor.id
                else:
                    partes_codigo.append("0" * atributo.longitud)

        codigo_final = "".join(partes_codigo)
        nombre_final = " ".join(partes_nombre) if partes_nombre else "Sin nombre"

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

        await db.delete(producto)
        await db.commit()
        return {"detail": "Producto eliminado exitosamente"}
    except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=str(e))