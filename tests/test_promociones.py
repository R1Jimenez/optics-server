from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from controllers import promociones_controller as api
from models.promociones_model import PromocionCreate


def _datos(**extra):
    base = dict(
        nombre="  Buen Fin  ", descuento=Decimal("15"), descuento_max_vendedor=Decimal("5"),
        fecha_inicio=date(2026, 11, 1), fecha_fin=date(2026, 11, 30), sucursales=[1, 2, 1],
    )
    base.update(extra)
    return PromocionCreate(**base)


# ---------- Reglas (sin BD) ----------

def test_normaliza_nombre_y_sucursales_repetidas():
    datos = api.normalizar_promocion(_datos())
    assert datos.nombre == "Buen Fin"
    assert datos.sucursales == [1, 2]


def test_permanente_ignora_vigencia():
    datos = api.normalizar_promocion(_datos(permanente=True))
    assert datos.fecha_inicio is None and datos.fecha_fin is None


def test_no_permanente_exige_vigencia():
    with pytest.raises(HTTPException) as exc:
        api.normalizar_promocion(_datos(fecha_fin=None))
    assert exc.value.status_code == 400


def test_fin_anterior_al_inicio():
    with pytest.raises(HTTPException):
        api.normalizar_promocion(_datos(fecha_inicio=date(2026, 12, 1), fecha_fin=date(2026, 11, 1)))


def test_descuento_vendedor_no_supera_descuento():
    with pytest.raises(HTTPException) as exc:
        api.normalizar_promocion(_datos(descuento_max_vendedor=Decimal("20")))
    assert "vendedor" in exc.value.detail


@pytest.mark.parametrize("campo, valor", [("descuento", 0), ("descuento", 101), ("descuento_max_vendedor", -1)])
def test_rangos_de_descuento(campo, valor):
    with pytest.raises(ValueError):
        _datos(**{campo: valor})


def test_requiere_al_menos_una_sucursal():
    with pytest.raises(ValueError):
        _datos(sucursales=[])


@pytest.mark.parametrize("permanente, inicio, fin, activo, esperado", [
    (True, None, None, True, True),
    (False, date(2026, 10, 1), date(2026, 10, 31), True, True),
    (False, date(2026, 11, 1), date(2026, 11, 30), True, False),
    (True, None, None, False, False),
])
def test_vigencia(permanente, inicio, fin, activo, esperado):
    p = SimpleNamespace(permanente=permanente, fecha_inicio=inicio, fecha_fin=fin, activo=activo)
    assert api.esta_vigente(p, hoy=date(2026, 10, 27)) is esperado


# ---------- Integracion (transaccion revertida, ver conftest) ----------

@pytest.mark.anyio
async def test_crear_y_listar_por_sucursal(db, escenario):
    e = escenario
    p = await api.crear_promocion(_datos(sucursales=[e["origen"].id]), db, e["usuario"])
    assert p.nombre == "Buen Fin"
    assert [s.sucursal for s in p.sucursales] == ["PRUEBA Origen"]
    assert p.creado_por == "prueba.traspasos"

    en_origen = await api.listar_promociones(sucursal_id=e["origen"].id, incluir_inactivas=False, db=db)
    en_destino = await api.listar_promociones(sucursal_id=e["destino"].id, incluir_inactivas=False, db=db)
    assert p.id in [x.id for x in en_origen]
    assert p.id not in [x.id for x in en_destino]


@pytest.mark.anyio
async def test_nombre_duplicado_entre_activas(db, escenario):
    e = escenario
    await api.crear_promocion(_datos(nombre="Promo Unica PRUEBA", sucursales=[e["origen"].id]), db, e["usuario"])
    with pytest.raises(HTTPException) as exc:
        await api.crear_promocion(_datos(nombre="promo unica prueba", sucursales=[e["destino"].id]), db, e["usuario"])
    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_actualizar_reemplaza_sucursales(db, escenario):
    e = escenario
    p = await api.crear_promocion(_datos(sucursales=[e["origen"].id]), db, e["usuario"])
    p = await api.actualizar_promocion(
        p.id, _datos(nombre="Buen Fin 2", permanente=True, sucursales=[e["destino"].id]), db, e["usuario"]
    )
    assert p.nombre == "Buen Fin 2"
    assert p.permanente and p.fecha_inicio is None
    assert [s.id for s in p.sucursales] == [e["destino"].id]


@pytest.mark.anyio
async def test_baja_logica(db, escenario):
    e = escenario
    # el rollback del endpoint al rechazar la edicion expira los objetos del escenario
    origen_id = e["origen"].id
    p = await api.crear_promocion(_datos(nombre="Promo Baja PRUEBA", sucursales=[origen_id]), db, e["usuario"])
    p = await api.baja_promocion(p.id, db, e["usuario"])
    assert p.activo is False and p.vigente is False

    activas = await api.listar_promociones(sucursal_id=origen_id, incluir_inactivas=False, db=db)
    assert p.id not in [x.id for x in activas]
    with pytest.raises(HTTPException):
        await api.actualizar_promocion(p.id, _datos(sucursales=[origen_id]), db, e["usuario"])

    # el nombre queda libre para una nueva promocion activa
    await api.crear_promocion(_datos(nombre="Promo Baja PRUEBA", sucursales=[origen_id]), db, e["usuario"])


@pytest.mark.anyio
async def test_sucursal_inexistente(db, escenario):
    e = escenario
    with pytest.raises(HTTPException) as exc:
        await api.crear_promocion(_datos(sucursales=[e["origen"].id, 999999]), db, e["usuario"])
    assert exc.value.status_code == 404
