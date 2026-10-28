from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from database.database import get_db
from middleware.auth import get_current_user
from models.promociones_model import (
    Promociones, PromocionSucursal, PromocionCondicion, PromocionCreate, PromocionOut, PromocionSucursalOut,
    PromocionReferenciaOut, CATEGORIAS_CONDICION, GRUPOS_CONDICION
)
from models.sucursales_model import Sucursal
from models.tipo_venta_model import TipoVenta
from models.plazo_model import Plazo
from models.producto_model import Productos
from models.atributos_model import Atributo
from models.atributos_valores_model import AtributosValores
from models.clientes_model import Cliente
from models.tipo_cliente_model import Tipo_Cliente

router = APIRouter(prefix="/promociones", tags=["Promociones"], dependencies=[Depends(get_current_user)])

NOMBRE_CATEGORIA = {
    "tipos_venta": "tipo de venta",
    "plazos": "plazo",
    "productos": "producto",
    "atributos_valores": "atributo de producto",
    "clientes": "cliente",
    "tipos_cliente": "tipo de cliente",
}


# ---------- Reglas de negocio (sin acceso a BD) ----------

def normalizar_promocion(datos: PromocionCreate) -> PromocionCreate:
    """Valida reglas entre campos y limpia los datos (nombre, ids repetidos, fechas de promociones permanentes)."""
    nombre = datos.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre de la promocion es obligatorio")

    if datos.descuento_max_vendedor > datos.descuento:
        raise HTTPException(
            status_code=400,
            detail="El descuento maximo del vendedor no puede ser mayor al descuento de la promocion"
        )

    for a, b in GRUPOS_CONDICION:
        if getattr(datos, a) and getattr(datos, b):
            raise HTTPException(
                status_code=400,
                detail=f"La promocion solo puede aplicar por {NOMBRE_CATEGORIA[a]} o por {NOMBRE_CATEGORIA[b]}, no por ambos"
            )

    fecha_inicio, fecha_fin = datos.fecha_inicio, datos.fecha_fin
    if datos.permanente:
        # una promocion permanente no tiene vigencia
        fecha_inicio = fecha_fin = None
    else:
        if not fecha_inicio or not fecha_fin:
            raise HTTPException(status_code=400, detail="Indique la fecha de inicio y fin de la vigencia, o marque la promocion como permanente")
        if fecha_fin < fecha_inicio:
            raise HTTPException(status_code=400, detail="La fecha de fin no puede ser anterior a la fecha de inicio")

    cambios = {
        "nombre": nombre,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "sucursales": list(dict.fromkeys(datos.sucursales)),
    }
    for categoria in CATEGORIAS_CONDICION:
        cambios[categoria] = list(dict.fromkeys(getattr(datos, categoria)))
    return datos.model_copy(update=cambios)


def esta_vigente(p: Promociones, hoy: date | None = None) -> bool:
    if not p.activo:
        return False
    if p.permanente:
        return True
    hoy = hoy or date.today()
    return bool(p.fecha_inicio and p.fecha_fin and p.fecha_inicio <= hoy <= p.fecha_fin)


def condiciones_por_categoria(p: Promociones) -> dict[str, set[int]]:
    resultado = {c: set() for c in CATEGORIAS_CONDICION}
    for cond in p.condiciones:
        resultado[cond.categoria].add(cond.referencia_id)
    return resultado


def motivo_no_aplica(
    cond: dict[str, set[int]], tipo_venta_id: int | None, plazo_id: int | None,
    cliente_id: int | None, tipo_cliente_id: int | None
) -> str | None:
    """None si la venta cumple las condiciones de tipo de venta, plazo y cliente; si no, el motivo."""
    if cond["tipos_venta"] and tipo_venta_id not in cond["tipos_venta"]:
        return "no aplica para el tipo de venta seleccionado"
    if cond["plazos"] and plazo_id not in cond["plazos"]:
        return "no aplica para el plazo seleccionado"
    if cond["clientes"] and cliente_id not in cond["clientes"]:
        return "no aplica para este cliente"
    if cond["tipos_cliente"] and tipo_cliente_id not in cond["tipos_cliente"]:
        return "no aplica para el tipo de cliente"
    return None


def producto_elegible(cond: dict[str, set[int]], producto_id: int, valores_producto: set[int]) -> bool:
    """Sin condiciones de producto aplica a todos; por atributo basta con que el producto tenga uno de los valores."""
    if cond["productos"]:
        return producto_id in cond["productos"]
    if cond["atributos_valores"]:
        return bool(cond["atributos_valores"] & valores_producto)
    return True


def porcentaje_descuento(pct_cliente, pct_promocion, acumulativa: bool, elegible: bool) -> Decimal:
    """Acumulativa: se suma al descuento del tipo de cliente (tope 100). No acumulativa: se aplica el mayor de los dos."""
    pct_cliente = Decimal(pct_cliente)
    if pct_promocion is None or not elegible:
        return pct_cliente
    if acumulativa:
        return min(Decimal("100"), pct_cliente + Decimal(pct_promocion))
    return max(pct_cliente, Decimal(pct_promocion))


# ---------- Acceso a datos ----------

# funcion (no constante) para no configurar los mappers al importar el modulo
def _opciones_carga():
    return (
        selectinload(Promociones.sucursales).selectinload(PromocionSucursal.sucursal),
        selectinload(Promociones.condiciones),
        selectinload(Promociones.creador),
        selectinload(Promociones.modificador),
    )


async def _cargar(db: AsyncSession, promocion_id: int) -> Promociones:
    result = await db.execute(
        select(Promociones)
        .options(*_opciones_carga())
        .where(Promociones.id == promocion_id)
        .execution_options(populate_existing=True)
    )
    promocion = result.scalar_one_or_none()
    if not promocion:
        raise HTTPException(status_code=404, detail="Promocion no encontrada")
    return promocion


async def cargar_promocion(db: AsyncSession, promocion_id: int) -> Promociones:
    return await _cargar(db, promocion_id)


async def _etiquetas(db: AsyncSession, categoria: str, ids) -> dict[int, str]:
    """Texto a mostrar para cada id referenciado por una condicion."""
    ids = list(ids)
    if not ids:
        return {}
    if categoria == "tipos_venta":
        filas = await db.execute(select(TipoVenta.id, TipoVenta.venta).where(TipoVenta.id.in_(ids)))
        return {i: v for i, v in filas.all()}
    if categoria == "plazos":
        filas = await db.execute(
            select(Plazo.id, Plazo.plazo, TipoVenta.venta)
            .outerjoin(TipoVenta, TipoVenta.id == Plazo.tipo_venta_id)
            .where(Plazo.id.in_(ids))
        )
        return {i: f"{p} ({v})" if v else p for i, p, v in filas.all()}
    if categoria == "productos":
        filas = await db.execute(select(Productos.id, Productos.codigo, Productos.nombre).where(Productos.id.in_(ids)))
        return {i: f"{c} - {n}" for i, c, n in filas.all()}
    if categoria == "atributos_valores":
        filas = await db.execute(
            select(AtributosValores.id, Atributo.atributo, AtributosValores.descripcion)
            .join(Atributo, Atributo.id == AtributosValores.atributo_id)
            .where(AtributosValores.id.in_(ids))
        )
        return {i: f"{a}: {d}" for i, a, d in filas.all()}
    if categoria == "clientes":
        filas = await db.execute(select(Cliente.id, Cliente.nombres, Cliente.apellidos).where(Cliente.id.in_(ids)))
        return {i: f"{n} {a}" for i, n, a in filas.all()}
    if categoria == "tipos_cliente":
        filas = await db.execute(select(Tipo_Cliente.id, Tipo_Cliente.cliente).where(Tipo_Cliente.id.in_(ids)))
        return {i: c for i, c in filas.all()}
    raise ValueError(categoria)


async def _validar_en_bd(db: AsyncSession, datos: PromocionCreate, excluir_id: int | None = None) -> None:
    result = await db.execute(select(Sucursal.id).where(Sucursal.id.in_(datos.sucursales)))
    existentes = set(result.scalars().all())
    faltantes = [str(s) for s in datos.sucursales if s not in existentes]
    if faltantes:
        raise HTTPException(status_code=404, detail=f"Sucursal no encontrada: {', '.join(faltantes)}")

    for categoria in CATEGORIAS_CONDICION:
        ids = getattr(datos, categoria)
        encontrados = await _etiquetas(db, categoria, ids)
        faltantes = [str(i) for i in ids if i not in encontrados]
        if faltantes:
            raise HTTPException(status_code=404, detail=f"No existe el {NOMBRE_CATEGORIA[categoria]} {', '.join(faltantes)}")

    query = select(Promociones.id).where(
        func.lower(Promociones.nombre) == datos.nombre.lower(),
        Promociones.activo.is_(True)
    )
    if excluir_id is not None:
        query = query.where(Promociones.id != excluir_id)
    if (await db.execute(query)).first():
        raise HTTPException(status_code=400, detail=f"Ya existe una promocion activa con el nombre '{datos.nombre}'")


async def _salidas(db: AsyncSession, promociones: list[Promociones]) -> list[PromocionOut]:
    # una consulta por categoria para todas las promociones
    ids_por_categoria = {c: set() for c in CATEGORIAS_CONDICION}
    for p in promociones:
        for cond in p.condiciones:
            ids_por_categoria[cond.categoria].add(cond.referencia_id)
    etiquetas = {c: await _etiquetas(db, c, ids) for c, ids in ids_por_categoria.items()}

    salidas = []
    for p in promociones:
        referencias = {c: [] for c in CATEGORIAS_CONDICION}
        for cond in p.condiciones:
            texto = etiquetas[cond.categoria].get(cond.referencia_id, f"#{cond.referencia_id} (eliminado)")
            referencias[cond.categoria].append(PromocionReferenciaOut(id=cond.referencia_id, etiqueta=texto))
        salidas.append(PromocionOut(
            id=p.id,
            nombre=p.nombre,
            descuento=p.descuento,
            descuento_max_vendedor=p.descuento_max_vendedor,
            acumulativa=p.acumulativa,
            permanente=p.permanente,
            fecha_inicio=p.fecha_inicio,
            fecha_fin=p.fecha_fin,
            activo=p.activo,
            vigente=esta_vigente(p),
            sucursales=[PromocionSucursalOut(id=ps.sucursal_id, sucursal=ps.sucursal.sucursal) for ps in p.sucursales],
            **referencias,
            creado_por=p.creador.usuario if p.creador else "N/A",
            fecha_creacion=p.fecha_creacion,
            modificado_por=p.modificador.usuario if p.modificador else "N/A",
            fecha_modificacion=p.fecha_modificacion,
        ))
    return salidas


async def _salida(db: AsyncSession, p: Promociones) -> PromocionOut:
    return (await _salidas(db, [p]))[0]


def _aplicar(p: Promociones, datos: PromocionCreate, usuario_id: int) -> None:
    p.nombre = datos.nombre
    p.descuento = datos.descuento
    p.descuento_max_vendedor = datos.descuento_max_vendedor
    p.acumulativa = datos.acumulativa
    p.permanente = datos.permanente
    p.fecha_inicio = datos.fecha_inicio
    p.fecha_fin = datos.fecha_fin
    p.sucursales = [PromocionSucursal(sucursal_id=sid) for sid in datos.sucursales]
    p.condiciones = [
        PromocionCondicion(categoria=categoria, referencia_id=ref_id)
        for categoria in CATEGORIAS_CONDICION
        for ref_id in getattr(datos, categoria)
    ]
    p.modificado_por = usuario_id
    p.fecha_modificacion = datetime.utcnow()


async def _tipo_cliente_de(db: AsyncSession, cliente_id: int | None) -> int | None:
    if cliente_id is None:
        return None
    return await db.scalar(select(Cliente.tipocliente).where(Cliente.id == cliente_id))


async def _candidatas(db: AsyncSession, sucursal_id: int) -> list[Promociones]:
    """Promociones activas de la sucursal; la vigencia se revisa en Python con esta_vigente."""
    result = await db.execute(
        select(Promociones)
        .options(*_opciones_carga())
        .where(
            Promociones.activo.is_(True),
            Promociones.sucursales.any(PromocionSucursal.sucursal_id == sucursal_id)
        )
        .order_by(Promociones.nombre)
    )
    return list(result.scalars().all())


async def obtener_promocion_aplicable(
    db: AsyncSession, promocion_id: int, sucursal_id: int, tipo_venta_id: int | None,
    plazo_id: int | None, cliente_id: int | None
) -> tuple[Promociones, dict[str, set[int]]]:
    """Para la cotizacion: devuelve la promocion y sus condiciones, o 400 explicando por que no aplica."""
    promocion = await _cargar(db, promocion_id)
    if not esta_vigente(promocion):
        raise HTTPException(status_code=400, detail=f"La promocion '{promocion.nombre}' no esta vigente")
    if sucursal_id not in {ps.sucursal_id for ps in promocion.sucursales}:
        raise HTTPException(status_code=400, detail=f"La promocion '{promocion.nombre}' no aplica en esta sucursal")
    cond = condiciones_por_categoria(promocion)
    motivo = motivo_no_aplica(cond, tipo_venta_id, plazo_id, cliente_id, await _tipo_cliente_de(db, cliente_id))
    if motivo:
        raise HTTPException(status_code=400, detail=f"La promocion '{promocion.nombre}' {motivo}")
    return promocion, cond


# ---------- Endpoints ----------

@router.get("/all", response_model=list[PromocionOut])
async def listar_promociones(
    sucursal_id: int | None = Query(None),
    incluir_inactivas: bool = Query(False),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Promociones).options(*_opciones_carga())
        if not incluir_inactivas:
            query = query.where(Promociones.activo.is_(True))
        if sucursal_id is not None:
            query = query.where(Promociones.sucursales.any(PromocionSucursal.sucursal_id == sucursal_id))
        result = await db.execute(query.order_by(Promociones.id.desc()))
        return await _salidas(db, list(result.scalars().all()))
    except Exception as e:
        print(f"Error al listar promociones: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/disponibles", response_model=list[PromocionOut])
async def promociones_disponibles(
    sucursal_id: int = Query(...),
    tipo_venta_id: int | None = Query(None),
    plazo_id: int | None = Query(None),
    cliente_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Promociones que se pueden aplicar hoy a una venta con estos datos (las de producto se resuelven por renglon)."""
    try:
        tipo_cliente_id = await _tipo_cliente_de(db, cliente_id)
        aplicables = [
            p for p in await _candidatas(db, sucursal_id)
            if esta_vigente(p) and motivo_no_aplica(
                condiciones_por_categoria(p), tipo_venta_id, plazo_id, cliente_id, tipo_cliente_id
            ) is None
        ]
        return await _salidas(db, aplicables)
    except Exception as e:
        print(f"Error al obtener promociones disponibles: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/{promocion_id}", response_model=PromocionOut)
async def get_promocion(promocion_id: int, db: AsyncSession = Depends(get_db)):
    try:
        return await _salida(db, await _cargar(db, promocion_id))
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al obtener promocion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.post("/create", response_model=PromocionOut)
async def crear_promocion(
    datos: PromocionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        datos = normalizar_promocion(datos)
        await _validar_en_bd(db, datos)
        promocion = Promociones(creado_por=current_user["id"], activo=True)
        _aplicar(promocion, datos, current_user["id"])
        db.add(promocion)
        await db.commit()
        return await _salida(db, await _cargar(db, promocion.id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear promocion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.put("/update/{promocion_id}", response_model=PromocionOut)
async def actualizar_promocion(
    promocion_id: int,
    datos: PromocionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        promocion = await _cargar(db, promocion_id)
        if not promocion.activo:
            raise HTTPException(status_code=400, detail="No se puede modificar una promocion dada de baja")
        datos = normalizar_promocion(datos)
        await _validar_en_bd(db, datos, excluir_id=promocion_id)
        _aplicar(promocion, datos, current_user["id"])
        await db.commit()
        return await _salida(db, await _cargar(db, promocion.id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar promocion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.delete("/delete/{promocion_id}", response_model=PromocionOut)
async def baja_promocion(
    promocion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Baja logica: la promocion deja de aplicar pero se conserva para el historial de ventas."""
    try:
        promocion = await _cargar(db, promocion_id)
        promocion.activo = False
        promocion.modificado_por = current_user["id"]
        promocion.fecha_modificacion = datetime.utcnow()
        await db.commit()
        return await _salida(db, await _cargar(db, promocion.id))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al dar de baja promocion: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
