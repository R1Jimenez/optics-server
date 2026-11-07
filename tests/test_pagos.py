"""Cobro del pago inicial en caja. Corre en una transaccion que se revierte (ver conftest.db)."""
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException

from controllers import pagos_controller as api
from controllers.abonos_controller import get_cuentas_por_cobrar
from controllers.cotizacion_controller import get_cotizaciones_en_espera, delete_cotizacion
from models.abonos_model import Abonos, AbonoItem
from models.clientes_model import Cliente
from models.cotizacion_model import Cotizaciones
from models.pacientes_model import Paciente
from models.pagos_model import PagoFormaIn, PagoInicialCreate, AbonosCobro
from models.plazo_model import Plazo
from models.tipo_venta_model import TipoVenta

pytestmark = pytest.mark.anyio


def formas(*pares):
    return [PagoFormaIn(forma=f, importe=Decimal(str(i))) for f, i in pares]


# ---------- Reglas (sin BD) ----------

@pytest.mark.parametrize("pares, recibido, cambio", [
    ([("Efectivo", 500)], 500, 0),
    ([("Efectivo", 600)], 600, 100),
    ([("Tarjeta de Crédito", 300), ("Efectivo", 250)], 550, 50),
])
def test_calcular_cobro(pares, recibido, cambio):
    assert api.calcular_cobro(Decimal("500"), formas(*pares)) == (Decimal(recibido), Decimal(cambio))


@pytest.mark.parametrize("pares, mensaje", [
    ([("Efectivo", 400)], "no cubre"),
    ([("Tarjeta de Crédito", 600)], "cambio en efectivo"),
    ([("Tarjeta de Crédito", 450), ("Efectivo", 20)], "no cubre"),
    ([("Tarjeta de Crédito", 520), ("Efectivo", 10)], "cambio en efectivo"),
    ([("Bitcoin", 500)], "no valida"),
    ([("Efectivo", 300), ("Efectivo", 200)], "repetida"),
])
def test_calcular_cobro_rechaza(pares, mensaje):
    with pytest.raises(HTTPException) as exc:
        api.calcular_cobro(Decimal("500"), formas(*pares))
    assert exc.value.status_code == 400 and mensaje in exc.value.detail


# ---------- Integracion ----------

@pytest.fixture
async def ventas(db, escenario):
    e = escenario
    tipo_venta = TipoVenta(venta="PRUEBA Contado")
    credito = TipoVenta(venta="PRUEBA Credito", es_credito=True)
    db.add_all([tipo_venta, credito])
    await db.flush()
    plazo = Plazo(plazo="Inmediato", tipo_venta_id=tipo_venta.id)
    clientes = [
        Cliente(nombres="Cliente", apellidos=f"Caja {i}", rfc="XAXX010101000", calle="-", numero="-", colonia="-",
                ciudad="-", estado="-", codigopostal="0", telefono="0", email=f"prueba.caja{i}@example.com",
                contacto="-", tipocliente=None)
        for i in (1, 2)
    ]
    db.add_all([plazo, *clientes])
    await db.flush()
    pacientes = [Paciente(nombres="Paciente", apellidos="Caja", edad=30, cliente_id=c.id) for c in clientes]
    db.add_all(pacientes)
    await db.flush()

    def cotizacion(cliente, paciente, total, inicial, tipo=None, **extra):
        return Cotizaciones(
            sucursal_id=e["origen"].id, usuario_id=e["usuario"]["id"], id_cliente=cliente.id, id_paciente=paciente.id,
            tipo_venta=tipo or tipo_venta.id, plazo=plazo.id, pago_inicial=Decimal(inicial),
            pago_restante=Decimal(total) - Decimal(inicial), fecha=datetime.utcnow(),
            total_normal=Decimal(total), total_venta=Decimal(total), **extra
        )

    a = cotizacion(clientes[0], pacientes[0], 500, 500)
    b = cotizacion(clientes[0], pacientes[0], 1000, 200)
    sin_inicial = cotizacion(clientes[0], pacientes[0], 300, 0)
    inactiva = cotizacion(clientes[0], pacientes[0], 100, 100, active=False)
    otro_cliente = cotizacion(clientes[1], pacientes[1], 100, 100)
    a_credito = cotizacion(clientes[0], pacientes[0], 400, 0, tipo=credito.id)
    db.add_all([a, b, sin_inicial, inactiva, otro_cliente, a_credito])
    await db.flush()
    return {
        "sucursal": e["origen"].id, "usuario": e["usuario"], "cliente": clientes[0].id,
        "a": a.id, "b": b.id, "sin_inicial": sin_inicial.id, "inactiva": inactiva.id, "otro_cliente": otro_cliente.id,
        "a_credito": a_credito.id,
    }


def _cobro(v, ids, *pares, observaciones=None):
    return PagoInicialCreate(sucursal_id=v["sucursal"], cotizacion_ids=ids, formas=formas(*pares), observaciones=observaciones)


async def test_pendientes_solo_con_pago_inicial_por_cobrar(db, ventas):
    v = ventas
    pendientes = await api.pagos_iniciales_pendientes(v["cliente"], db)
    assert [p.id for p in pendientes] == [v["a"], v["b"]]
    assert (pendientes[1].tipo_venta, pendientes[1].plazo) == ("PRUEBA Contado", "Inmediato")
    assert (pendientes[1].total_venta, pendientes[1].pago_inicial) == (Decimal("1000"), Decimal("200"))

    en_espera = {c.id for c in await get_cotizaciones_en_espera(v["sucursal"], db)}
    assert {v["a"], v["b"], v["otro_cliente"]} <= en_espera
    assert not ({v["sin_inicial"], v["inactiva"]} & en_espera)


async def test_cobra_varios_presupuestos_con_cambio(db, ventas):
    v = ventas
    pago = await api.cobrar_pago_inicial(
        _cobro(v, [v["a"], v["b"]], ("Tarjeta de Crédito", 300), ("Efectivo", 450), observaciones="  Paga en mostrador "),
        db, v["usuario"]
    )
    assert (pago.total, pago.recibido, pago.cambio) == (Decimal("700"), Decimal("750"), Decimal("50"))
    assert pago.observaciones == "Paga en mostrador"
    assert [(f.forma, f.importe) for f in pago.formas] == [("Tarjeta de Crédito", Decimal("300")), ("Efectivo", Decimal("450"))]
    assert pago.cotizacion_ids == [v["a"], v["b"]]

    assert await api.pagos_iniciales_pendientes(v["cliente"], db) == []
    assert not ({v["a"], v["b"]} & {c.id for c in await get_cotizaciones_en_espera(v["sucursal"], db)})

    with pytest.raises(HTTPException) as exc:
        await api.cobrar_pago_inicial(_cobro(v, [v["a"]], ("Efectivo", 500)), db, v["usuario"])
    assert "ya fue cobrado" in exc.value.detail

    with pytest.raises(HTTPException) as exc:
        await delete_cotizacion(v["a"], db, v["usuario"])
    assert exc.value.status_code == 400


@pytest.mark.parametrize("clave, mensaje", [
    ("otro_cliente", "mismo cliente"),
    ("inactiva", "no esta activo"),
    ("sin_inicial", "no tiene pago inicial"),
])
async def test_rechaza_presupuestos_invalidos(db, ventas, clave, mensaje):
    v = ventas
    with pytest.raises(HTTPException) as exc:
        await api.cobrar_pago_inicial(_cobro(v, [v["a"], v[clave]], ("Efectivo", 1000)), db, v["usuario"])
    assert mensaje in exc.value.detail


async def test_no_cobra_si_no_cubre_el_total(db, ventas):
    v = ventas
    with pytest.raises(HTTPException) as exc:
        await api.cobrar_pago_inicial(_cobro(v, [v["a"]], ("Efectivo", 499.99)), db, v["usuario"])
    assert "no cubre" in exc.value.detail


# ---------- Pagos parciales y abonos en caja ----------

def _abonos(v, montos, *pares):
    return AbonosCobro(
        sucursal_id=v["sucursal"],
        abonos=[AbonoItem(cotizacion_id=i, monto=Decimal(str(m))) for i, m in montos],
        formas=formas(*pares),
    )


async def test_parciales_tras_cobrar_el_pago_inicial(db, ventas):
    v = ventas
    # b tiene pago inicial pendiente: aun no se abona
    assert [p.id for p in await api.pagos_parciales_pendientes(v["cliente"], db)] == [v["sin_inicial"], v["a_credito"]]

    await api.cobrar_pago_inicial(_cobro(v, [v["a"], v["b"]], ("Efectivo", 700)), db, v["usuario"])
    parciales = {p.id: p for p in await api.pagos_parciales_pendientes(v["cliente"], db)}
    # a quedo liquidada; las ventas a credito aparecen en ambas pestañas
    assert set(parciales) == {v["b"], v["sin_inicial"], v["a_credito"]}
    assert (parciales[v["a_credito"]].total_pagado, parciales[v["a_credito"]].diferencia) == (Decimal("0"), Decimal("400"))
    assert (parciales[v["b"]].total_venta, parciales[v["b"]].total_pagado, parciales[v["b"]].diferencia) == (
        Decimal("1000"), Decimal("200"), Decimal("800")
    )
    assert [c.id for c in await get_cuentas_por_cobrar(v["cliente"], db)] == [v["a_credito"]]


async def test_abonos_en_caja_con_formas_de_pago(db, ventas):
    v = ventas
    await api.cobrar_pago_inicial(_cobro(v, [v["b"]], ("Efectivo", 200)), db, v["usuario"])
    pago = await api.cobrar_abonos(
        _abonos(v, [(v["b"], 300), (v["sin_inicial"], 100)], ("Tarjeta de Crédito", 350), ("Efectivo", 100)),
        db, v["usuario"]
    )
    assert (pago.tipo, pago.total, pago.recibido, pago.cambio) == ("abono", Decimal("400"), Decimal("450"), Decimal("50"))

    parciales = {p.id: p for p in await api.pagos_parciales_pendientes(v["cliente"], db)}
    assert (parciales[v["b"]].total_pagado, parciales[v["b"]].diferencia) == (Decimal("500"), Decimal("500"))
    assert [a.monto for a in parciales[v["sin_inicial"]].abonos] == [Decimal("100")]
    abono = await db.get(Abonos, parciales[v["b"]].abonos[0].id)
    assert abono.pago_id == pago.id


@pytest.mark.parametrize("montos, mensaje", [
    (lambda v: [(v["sin_inicial"], 300.01)], "excede el saldo"),
    (lambda v: [(v["b"], 100)], "Primero cobre el pago inicial"),
    (lambda v: [(v["sin_inicial"], 10), (v["sin_inicial"], 10)], "mas de una vez"),
])
async def test_abonos_rechazados(db, ventas, montos, mensaje):
    v = ventas
    with pytest.raises(HTTPException) as exc:
        await api.cobrar_abonos(_abonos(v, montos(v), ("Efectivo", 1000)), db, v["usuario"])
    assert mensaje in exc.value.detail


# ---------- Liquidaciones ----------

async def test_liquidaciones_ventas_pagadas_por_completo(db, ventas):
    v = ventas
    assert (await api.liquidaciones_cliente(v["cliente"], 1, 10, db)).total == 0

    cobro_inicial = await api.cobrar_pago_inicial(_cobro(v, [v["a"], v["b"]], ("Efectivo", 700)), db, v["usuario"])
    abono = await api.cobrar_abonos(
        _abonos(v, [(v["sin_inicial"], 300), (v["b"], 100)], ("Tarjeta de Crédito", 400)), db, v["usuario"]
    )
    # a quedo pagada con el pago inicial; sin_inicial con el abono; b aun debe
    pagina = await api.liquidaciones_cliente(v["cliente"], 1, 10, db)
    assert pagina.total == 2
    por_id = {i.id: i for i in pagina.items}
    assert set(por_id) == {v["a"], v["sin_inicial"]}
    assert (por_id[v["a"]].ticket, por_id[v["a"]].importe_total) == (cobro_inicial.id, Decimal("500"))
    assert por_id[v["sin_inicial"]].ticket == abono.id
    # la mas reciente primero
    assert pagina.items[0].fecha_liquidacion >= pagina.items[1].fecha_liquidacion

    segunda = await api.liquidaciones_cliente(v["cliente"], 2, 1, db)
    assert (segunda.total, len(segunda.items)) == (2, 1)

    detalle = await api.detalle_liquidacion(v["sin_inicial"], db)
    assert [(p.concepto, p.monto, p.cobro_id) for p in detalle.pagos] == [("Abono", Decimal("300"), abono.id)]
    assert [(f.forma, f.importe) for f in detalle.pagos[0].formas] == [("Tarjeta de Crédito", Decimal("400"))]
    assert detalle.pagos[0].cobro_total == Decimal("400")

    detalle_a = await api.detalle_liquidacion(v["a"], db)
    assert [(p.concepto, p.monto) for p in detalle_a.pagos] == [("Pago inicial", Decimal("500"))]

    assert (await api.marcar_liquidacion_impresa(v["a"], db))["impresa"] is True
    assert {i.id: i.impresa for i in (await api.liquidaciones_cliente(v["cliente"], 1, 10, db)).items}[v["a"]] is True


async def test_saldo_cancelado_no_es_liquidacion(db, ventas):
    v = ventas
    from controllers.abonos_controller import marcar_incobrable
    await marcar_incobrable(v["sin_inicial"], db, v["usuario"])
    assert (await api.liquidaciones_cliente(v["cliente"], 1, 10, db)).total == 0
    with pytest.raises(HTTPException) as exc:
        await api.detalle_liquidacion(v["sin_inicial"], db)
    assert exc.value.status_code == 404
