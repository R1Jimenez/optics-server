"""Condiciones de promociones (tipo de venta/plazo, producto/atributo, cliente/tipo de cliente) y su efecto en la cotizacion."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from controllers import promociones_controller as api
from controllers.cotizacion_controller import create_cotizacion
from models.promociones_model import PromocionCreate
from models.cotizacion_model import CotizacionCreate, CotizacionDetalleCreate
from models.tipo_venta_model import TipoVenta
from models.plazo_model import Plazo
from models.tipo_cliente_model import Tipo_Cliente
from models.clientes_model import Cliente
from models.pacientes_model import Paciente
from models.precios_sucursal_model import PreciosSucursal
from models.producto_model import ProductoAtributo
from models.atributos_model import Atributo
from models.atributos_valores_model import AtributosValores

VACIO = {c: set() for c in ("tipos_venta", "plazos", "productos", "atributos_valores", "clientes", "tipos_cliente")}


def cond(**valores):
    return {**VACIO, **{k: set(v) for k, v in valores.items()}}


# ---------- Reglas (sin BD) ----------

def test_no_permite_dos_criterios_del_mismo_grupo():
    with pytest.raises(HTTPException) as exc:
        api.normalizar_promocion(PromocionCreate(
            nombre="X", descuento=10, permanente=True, sucursales=[1], tipos_venta=[1], plazos=[2]
        ))
    assert "tipo de venta o por plazo" in exc.value.detail


def test_normaliza_ids_repetidos_de_condiciones():
    datos = api.normalizar_promocion(PromocionCreate(nombre="X", descuento=10, permanente=True, sucursales=[1], productos=[5, 5, 6]))
    assert datos.productos == [5, 6]


@pytest.mark.parametrize("condiciones, contexto, motivo", [
    (cond(), (1, 1, 1, 1), None),
    (cond(tipos_venta=[2]), (1, 1, 1, 1), "tipo de venta"),
    (cond(tipos_venta=[2]), (2, 1, 1, 1), None),
    (cond(plazos=[3]), (2, 4, 1, 1), "plazo"),
    (cond(clientes=[9]), (1, 1, 8, 1), "cliente"),
    (cond(tipos_cliente=[5]), (1, 1, 8, 5), None),
    (cond(tipos_cliente=[5]), (1, 1, None, None), "tipo de cliente"),
])
def test_motivo_no_aplica(condiciones, contexto, motivo):
    resultado = api.motivo_no_aplica(condiciones, *contexto)
    assert resultado is None if motivo is None else motivo in resultado


def test_producto_elegible():
    assert api.producto_elegible(cond(), 1, set())
    assert api.producto_elegible(cond(productos=[1]), 1, set())
    assert not api.producto_elegible(cond(productos=[1]), 2, set())
    assert api.producto_elegible(cond(atributos_valores=[7, 8]), 2, {8, 50})
    assert not api.producto_elegible(cond(atributos_valores=[7]), 2, {50})


@pytest.mark.parametrize("cliente, promo, acumulativa, elegible, esperado", [
    (10, 20, False, True, 20),
    (25, 20, False, True, 25),
    (10, 20, True, True, 30),
    (90, 20, True, True, 100),
    (10, 20, True, False, 10),
    (10, None, False, True, 10),
])
def test_porcentaje_descuento(cliente, promo, acumulativa, elegible, esperado):
    assert api.porcentaje_descuento(cliente, promo, acumulativa, elegible) == Decimal(esperado)


# ---------- Integracion (transaccion revertida, ver conftest) ----------

@pytest.fixture
async def venta(db, escenario):
    """Catalogos minimos para vender p1 y p2 en la sucursal origen a un cliente con 10% de descuento."""
    e = escenario
    tipo_venta = TipoVenta(venta="PRUEBA Credito")
    tipo_cliente = Tipo_Cliente(cliente="PRUEBA Frecuente", porcentaje_descuento=10)
    atributo = Atributo(atributo="PRUEBA Marca", longitud=2)
    db.add_all([tipo_venta, tipo_cliente, atributo])
    await db.flush()

    plazo = Plazo(plazo="4 semanas", tipo_venta_id=tipo_venta.id)
    cliente = Cliente(
        nombres="Cliente", apellidos="Prueba", rfc="XAXX010101000", calle="-", numero="-", colonia="-",
        ciudad="-", estado="-", codigopostal="0", telefono="0", email="cliente.prueba.promo@example.com",
        contacto="-", tipocliente=tipo_cliente.id
    )
    valor = AtributosValores(atributo_id=atributo.id, clave="99", descripcion="PRUEBA RayBan")
    db.add_all([plazo, cliente, valor])
    await db.flush()

    paciente = Paciente(nombres="Paciente", apellidos="Prueba", edad=30, cliente_id=cliente.id)
    db.add_all([
        paciente,
        PreciosSucursal(sucursal=e["origen"].id, producto=e["p1"].id, costo=50, precio=100),
        PreciosSucursal(sucursal=e["origen"].id, producto=e["p2"].id, costo=100, precio=200),
        ProductoAtributo(producto_id=e["p2"].id, atributo_id=atributo.id, atributovalor_id=valor.id),
    ])
    await db.flush()
    return {
        **e, "tipo_venta": tipo_venta.id, "plazo": plazo.id, "cliente": cliente.id,
        "tipo_cliente": tipo_cliente.id, "paciente": paciente.id, "valor": valor.id,
    }


def _promo(v, **extra):
    datos = dict(nombre="PRUEBA Promo", descuento=Decimal("20"), permanente=True, sucursales=[v["origen"].id])
    datos.update(extra)
    return PromocionCreate(**datos)


def _cotizacion(v, promocion_id):
    return CotizacionCreate(
        sucursal_id=v["origen"].id, usuario_id=v["usuario"]["id"], id_cliente=v["cliente"], id_paciente=v["paciente"],
        tipo_venta=v["tipo_venta"], plazo=v["plazo"], pago_inicial=Decimal("0"), promocion_id=promocion_id,
        productos=[CotizacionDetalleCreate(producto_id=v["p1"].id, cantidad=1), CotizacionDetalleCreate(producto_id=v["p2"].id, cantidad=1)],
    )


@pytest.mark.anyio
async def test_condiciones_se_guardan_con_etiquetas(db, venta):
    v = venta
    p = await api.crear_promocion(_promo(v, tipos_venta=[v["tipo_venta"]], atributos_valores=[v["valor"]], tipos_cliente=[v["tipo_cliente"]]), db, v["usuario"])
    assert [r.etiqueta for r in p.tipos_venta] == ["PRUEBA Credito"]
    assert [r.etiqueta for r in p.atributos_valores] == ["PRUEBA Marca: PRUEBA RayBan"]
    assert [r.etiqueta for r in p.tipos_cliente] == ["PRUEBA Frecuente"]
    assert p.productos == [] and p.plazos == []


@pytest.mark.anyio
async def test_disponibles_filtra_por_condiciones(db, venta):
    v = venta
    general = await api.crear_promocion(_promo(v, nombre="PRUEBA General"), db, v["usuario"])
    por_cliente = await api.crear_promocion(_promo(v, nombre="PRUEBA Cliente", clientes=[v["cliente"]]), db, v["usuario"])
    vencida = await api.crear_promocion(
        _promo(v, nombre="PRUEBA Vencida", permanente=False, fecha_inicio=date(2020, 1, 1), fecha_fin=date(2020, 1, 31)), db, v["usuario"]
    )

    con_cliente = await api.promociones_disponibles(v["origen"].id, v["tipo_venta"], v["plazo"], v["cliente"], db)
    sin_cliente = await api.promociones_disponibles(v["origen"].id, v["tipo_venta"], v["plazo"], None, db)
    otra_sucursal = await api.promociones_disponibles(v["destino"].id, v["tipo_venta"], v["plazo"], v["cliente"], db)

    ids = lambda lista: {p.id for p in lista}
    assert {general.id, por_cliente.id} <= ids(con_cliente)
    assert vencida.id not in ids(con_cliente)
    assert general.id in ids(sin_cliente) and por_cliente.id not in ids(sin_cliente)
    assert not ({general.id, por_cliente.id} & ids(otra_sucursal))


@pytest.mark.anyio
@pytest.mark.parametrize("acumulativa, pct_p1, pct_p2, total", [
    (False, 20, 10, Decimal("260.00")),  # p1: 100 - 20%, p2 (no elegible): 200 - 10%
    (True, 30, 10, Decimal("250.00")),   # p1: 100 - 30%
])
async def test_cotizacion_aplica_promocion_por_producto(db, venta, acumulativa, pct_p1, pct_p2, total):
    v = venta
    promo = await api.crear_promocion(_promo(v, acumulativa=acumulativa, productos=[v["p1"].id]), db, v["usuario"])
    cot = await create_cotizacion(_cotizacion(v, promo.id), db, v["usuario"])

    pcts = {d.producto_id: d.descuento_porcentaje for d in cot.detalles}
    assert pcts == {v["p1"].id: Decimal(pct_p1), v["p2"].id: Decimal(pct_p2)}
    assert cot.total_normal == Decimal("300.00")
    assert cot.total_venta == total
    assert cot.promocion_id == promo.id


@pytest.mark.anyio
async def test_cotizacion_aplica_promocion_por_atributo(db, venta):
    v = venta
    promo = await api.crear_promocion(_promo(v, atributos_valores=[v["valor"]]), db, v["usuario"])
    cot = await create_cotizacion(_cotizacion(v, promo.id), db, v["usuario"])
    pcts = {d.producto_id: d.descuento_porcentaje for d in cot.detalles}
    assert pcts == {v["p1"].id: Decimal(10), v["p2"].id: Decimal(20)}


@pytest.mark.anyio
async def test_cotizacion_rechaza_promocion_que_no_aplica(db, venta):
    v = venta
    otro_tipo = TipoVenta(venta="PRUEBA Contado")
    db.add(otro_tipo)
    await db.flush()
    otro_tipo_id = otro_tipo.id
    promo = await api.crear_promocion(_promo(v, tipos_venta=[otro_tipo_id]), db, v["usuario"])
    with pytest.raises(HTTPException) as exc:
        await create_cotizacion(_cotizacion(v, promo.id), db, v["usuario"])
    assert exc.value.status_code == 400
    assert "tipo de venta" in exc.value.detail


@pytest.mark.anyio
async def test_cotizacion_sin_promocion_conserva_descuento_de_cliente(db, venta):
    v = venta
    cot = await create_cotizacion(_cotizacion(v, None), db, v["usuario"])
    assert cot.total_venta == Decimal("270.00")
    assert all(d.descuento_porcentaje == Decimal(10) for d in cot.detalles)
