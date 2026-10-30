"""Catalogo de tipos de cliente. Corre en una transaccion que se revierte (ver conftest.db)."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from controllers import tipo_cliente_controller as api
from models.clientes_model import Cliente
from models.promociones_model import Promociones, PromocionCondicion
from models.tipo_cliente_model import TipoClienteCreate, TipoClienteUpdate
from models.users_model import User

pytestmark = pytest.mark.anyio


async def _crear(db, nombre, pct=10):
    return await api.create_tipo_cliente(TipoClienteCreate(cliente=nombre, porcentaje_descuento=pct), db)


def _cliente(tipo_id, n=1):
    return Cliente(
        nombres="Cliente", apellidos=f"Prueba {n}", rfc="XAXX010101000", calle="-", numero="-", colonia="-",
        ciudad="-", estado="-", codigopostal="0", telefono="0", email=f"prueba.tipocli{n}@example.com",
        contacto="-", tipocliente=tipo_id,
    )


async def _promocion(db, tipo_id, activo=True):
    usuario = User(
        nombres="Prueba", apellidos="Tipos", usuario=f"prueba.tipos.{activo}", email=f"prueba.tipos.{activo}@example.com",
        telefono="0", Sucursal=0, sucursal_acces=[], roles=[], hashed_password="x"
    )
    db.add(usuario)
    await db.flush()
    p = Promociones(nombre="PRUEBA promo", descuento=10, activo=activo, creado_por=usuario.id, modificado_por=usuario.id)
    p.condiciones = [PromocionCondicion(categoria="tipos_cliente", referencia_id=tipo_id)]
    db.add(p)
    await db.flush()


def test_validaciones_de_esquema():
    assert TipoClienteCreate(cliente="  Mayoreo  ", porcentaje_descuento=5).cliente == "Mayoreo"
    for datos in ({"cliente": "   ", "porcentaje_descuento": 5},
                  {"cliente": "X", "porcentaje_descuento": 101},
                  {"cliente": "X", "porcentaje_descuento": -1}):
        with pytest.raises(ValidationError):
            TipoClienteCreate(**datos)


async def test_no_permite_duplicados_sin_importar_mayusculas(db):
    t = await _crear(db, "PRUEBA Frecuente")
    with pytest.raises(HTTPException) as exc:
        await _crear(db, "prueba frecuente")
    assert exc.value.status_code == 400

    otro = await _crear(db, "PRUEBA Mayoreo")
    with pytest.raises(HTTPException):
        await api.update_tipo_cliente(otro.id, TipoClienteUpdate(cliente="PRUEBA FRECUENTE"), db)
    # renombrar el mismo registro (solo cambia mayusculas) si se permite
    actualizado = await api.update_tipo_cliente(t.id, TipoClienteUpdate(cliente="PRUEBA FRECUENTE", porcentaje_descuento=15), db)
    assert (actualizado.cliente, actualizado.porcentaje_descuento) == ("PRUEBA FRECUENTE", 15)


async def test_inexistente_responde_404(db):
    with pytest.raises(HTTPException) as exc:
        await api.get_tipo_cliente(-1, db)
    assert exc.value.status_code == 404


async def test_listado_ordenado_con_clientes_asignados(db):
    b = await _crear(db, "PRUEBA b tipo")
    a = await _crear(db, "PRUEBA A tipo")
    db.add_all([_cliente(b.id, 1), _cliente(b.id, 2)])
    await db.flush()

    tipos = [t for t in await api.get_all_tipo_clientes(db) if t.cliente.startswith("PRUEBA")]
    assert [(t.cliente, t.clientes) for t in tipos] == [("PRUEBA A tipo", 0), ("PRUEBA b tipo", 2)]
    assert a.id != b.id


async def test_no_elimina_si_tiene_clientes(db):
    t = await _crear(db, "PRUEBA Con clientes")
    tipo_id = t.id
    db.add(_cliente(tipo_id))
    await db.flush()
    with pytest.raises(HTTPException) as exc:
        await api.delete_tipo_cliente(tipo_id, db)
    assert exc.value.status_code == 400
    assert "1 cliente(s)" in exc.value.detail


async def test_no_elimina_si_lo_usa_una_promocion_activa(db):
    t = await _crear(db, "PRUEBA Con promo")
    tipo_id = t.id
    await _promocion(db, tipo_id)
    with pytest.raises(HTTPException) as exc:
        await api.delete_tipo_cliente(tipo_id, db)
    assert "1 promoción(es) activa(s)" in exc.value.detail


async def test_elimina_si_no_esta_en_uso(db):
    t = await _crear(db, "PRUEBA Libre")
    tipo_id = t.id
    await _promocion(db, tipo_id, activo=False)
    await api.delete_tipo_cliente(tipo_id, db)
    with pytest.raises(HTTPException) as exc:
        await api.get_tipo_cliente(tipo_id, db)
    assert exc.value.status_code == 404
