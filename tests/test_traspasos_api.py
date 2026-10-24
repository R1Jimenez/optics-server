"""Pruebas de integracion contra PostgreSQL. Todo corre en una transaccion que se revierte (ver conftest.db)."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from controllers import traspasos_controller as api
from controllers.inventario_controller import buscar_productos_sucursal
from models.inventario_model import InventarioSucursal, InventarioMovimiento
from models.traspasos_model import TraspasoCreate, TraspasoItem

pytestmark = pytest.mark.anyio


def _solicitud(e, *items, **extra):
    return TraspasoCreate(
        sucursal_origen_id=e["origen"].id,
        sucursal_destino_id=e["destino"].id,
        productos=[TraspasoItem(producto_id=p.id, cantidad=c) for p, c in items],
        **extra
    )


async def _existencia(db, sucursal_id, producto_id):
    inv = (await db.execute(select(InventarioSucursal).where(
        InventarioSucursal.sucursal_id == sucursal_id,
        InventarioSucursal.producto_id == producto_id
    ).execution_options(populate_existing=True))).scalar_one_or_none()
    return None if inv is None else inv.existencia_actual


async def test_crear_queda_nuevo_sin_mover_inventario(db, escenario):
    e = escenario
    t = await api.crear_traspaso(_solicitud(e, (e["p1"], 2), (e["p1"], 1), comentarios="Para exhibicion"), db, e["usuario"])

    assert t.estatus == "Nuevo"
    assert t.comentarios == "Para exhibicion"
    assert t.creado_por == "prueba.traspasos"
    assert [(d.producto_id, d.cantidad_solicitada) for d in t.detalles] == [(e["p1"].id, 3)]
    assert t.detalles[0].existencia_origen == 10
    assert await _existencia(db, e["origen"].id, e["p1"].id) == 10


async def test_no_permite_mas_que_la_existencia(db, escenario):
    e = escenario
    with pytest.raises(HTTPException) as exc:
        await api.crear_traspaso(_solicitud(e, (e["p2"], 4)), db, e["usuario"])
    assert exc.value.status_code == 400
    assert "solo hay 3" in exc.value.detail


async def test_no_permite_mismo_origen_y_destino(db, escenario):
    e = escenario
    datos = _solicitud(e, (e["p1"], 1))
    datos.sucursal_destino_id = datos.sucursal_origen_id
    with pytest.raises(HTTPException) as exc:
        await api.crear_traspaso(datos, db, e["usuario"])
    assert exc.value.status_code == 400


async def test_flujo_completo_enviar_y_recibir(db, escenario):
    e = escenario
    t = await api.crear_traspaso(_solicitud(e, (e["p1"], 4), (e["p2"], 3)), db, e["usuario"])

    t = await api.enviar_traspaso(t.id, db, e["usuario"])
    assert t.estatus == "Enviado"
    assert await _existencia(db, e["origen"].id, e["p1"].id) == 6
    assert await _existencia(db, e["origen"].id, e["p2"].id) == 0
    assert all(d.cantidad_enviada == d.cantidad_solicitada for d in t.detalles)

    t = await api.recibir_traspaso(t.id, db, e["usuario"])
    assert t.estatus == "Recibido"
    # el destino no manejaba los productos: se crea su inventario
    assert await _existencia(db, e["destino"].id, e["p1"].id) == 4
    assert await _existencia(db, e["destino"].id, e["p2"].id) == 3
    assert all(d.cantidad_recibida == d.cantidad_enviada for d in t.detalles)

    movimientos = (await db.execute(
        select(InventarioMovimiento.tipo, InventarioMovimiento.referencia)
        .where(InventarioMovimiento.referencia == f"Traspaso {t.id}")
    )).all()
    tipos = sorted(m.tipo for m in movimientos)
    assert tipos == ["Entrada por Traspaso", "Entrada por Traspaso", "Salida por Traspaso", "Salida por Traspaso"]


async def test_cancelar_enviado_regresa_mercancia(db, escenario):
    e = escenario
    t = await api.crear_traspaso(_solicitud(e, (e["p1"], 5)), db, e["usuario"])
    await api.enviar_traspaso(t.id, db, e["usuario"])
    assert await _existencia(db, e["origen"].id, e["p1"].id) == 5

    t = await api.cancelar_traspaso(t.id, db, e["usuario"])
    assert t.estatus == "Cancelado"
    assert await _existencia(db, e["origen"].id, e["p1"].id) == 10


async def test_no_se_edita_despues_de_enviar(db, escenario):
    e = escenario
    t = await api.crear_traspaso(_solicitud(e, (e["p1"], 1)), db, e["usuario"])
    await api.enviar_traspaso(t.id, db, e["usuario"])
    with pytest.raises(HTTPException) as exc:
        await api.actualizar_traspaso(t.id, _solicitud(e, (e["p1"], 2)), db, e["usuario"])
    assert exc.value.status_code == 400


async def test_editar_reemplaza_productos(db, escenario):
    e = escenario
    t = await api.crear_traspaso(_solicitud(e, (e["p1"], 1)), db, e["usuario"])
    t = await api.actualizar_traspaso(t.id, _solicitud(e, (e["p2"], 2), comentarios="Cambio"), db, e["usuario"])
    assert t.comentarios == "Cambio"
    assert [(d.producto_id, d.cantidad_solicitada) for d in t.detalles] == [(e["p2"].id, 2)]


async def test_enviar_revalida_existencia(db, escenario):
    e = escenario
    t = await api.crear_traspaso(_solicitud(e, (e["p2"], 3)), db, e["usuario"])
    inv = (await db.execute(select(InventarioSucursal).where(
        InventarioSucursal.sucursal_id == e["origen"].id, InventarioSucursal.producto_id == e["p2"].id
    ))).scalar_one()
    inv.existencia_actual = 1  # se vendio mercancia despues de capturar el traspaso
    await db.flush()

    with pytest.raises(HTTPException) as exc:
        await api.enviar_traspaso(t.id, db, e["usuario"])
    assert exc.value.status_code == 400


async def test_listado_filtra_por_estatus_y_origen(db, escenario):
    e = escenario
    t1 = await api.crear_traspaso(_solicitud(e, (e["p1"], 1)), db, e["usuario"])
    t2 = await api.crear_traspaso(_solicitud(e, (e["p1"], 1)), db, e["usuario"])
    await api.enviar_traspaso(t2.id, db, e["usuario"])

    pagina = await api.listar_traspasos(estatus="Enviado", origen_id=e["origen"].id, destino_id=None, pagina=1, por_pagina=10, db=db)
    assert [t.id for t in pagina.items] == [t2.id]

    pagina = await api.listar_traspasos(estatus=None, origen_id=e["origen"].id, destino_id=e["destino"].id, pagina=1, por_pagina=10, db=db)
    assert pagina.total == 2 and {t.id for t in pagina.items} == {t1.id, t2.id}


@pytest.mark.parametrize("termino", ["PRUEBA00000000000001", "producto prueba 1", "ext-prueba-1"])
async def test_buscar_por_codigo_nombre_o_codigo_externo(db, escenario, termino):
    e = escenario
    resultados = await buscar_productos_sucursal(e["origen"].id, termino, 15, db)
    assert [r.producto_id for r in resultados] == [e["p1"].id]
    assert resultados[0].existencia_actual == 10
