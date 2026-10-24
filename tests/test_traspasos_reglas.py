import pytest
from fastapi import HTTPException

from controllers.traspasos_controller import (
    consolidar_productos, validar_sucursales, validar_transicion, validar_existencias
)
from models.traspasos_model import (
    TraspasoItem, ESTATUS_NUEVO, ESTATUS_ENVIADO, ESTATUS_RECIBIDO, ESTATUS_CANCELADO
)


def test_consolidar_suma_renglones_del_mismo_producto():
    items = [TraspasoItem(producto_id=1, cantidad=2), TraspasoItem(producto_id=2, cantidad=1), TraspasoItem(producto_id=1, cantidad=3)]
    assert consolidar_productos(items) == {1: 5, 2: 1}


def test_item_rechaza_cantidad_cero_o_negativa():
    with pytest.raises(ValueError):
        TraspasoItem(producto_id=1, cantidad=0)
    with pytest.raises(ValueError):
        TraspasoItem(producto_id=1, cantidad=-1)


def test_origen_y_destino_iguales():
    with pytest.raises(HTTPException) as exc:
        validar_sucursales(3, 3)
    assert exc.value.status_code == 400
    validar_sucursales(1, 2)


@pytest.mark.parametrize("estatus, accion, permitido", [
    (ESTATUS_NUEVO, "editar", True),
    (ESTATUS_NUEVO, "enviar", True),
    (ESTATUS_NUEVO, "recibir", False),
    (ESTATUS_NUEVO, "cancelar", True),
    (ESTATUS_ENVIADO, "editar", False),
    (ESTATUS_ENVIADO, "enviar", False),
    (ESTATUS_ENVIADO, "recibir", True),
    (ESTATUS_ENVIADO, "cancelar", True),
    (ESTATUS_RECIBIDO, "cancelar", False),
    (ESTATUS_RECIBIDO, "editar", False),
    (ESTATUS_CANCELADO, "enviar", False),
    (ESTATUS_CANCELADO, "cancelar", False),
])
def test_transiciones(estatus, accion, permitido):
    if permitido:
        validar_transicion(estatus, accion)
    else:
        with pytest.raises(HTTPException) as exc:
            validar_transicion(estatus, accion)
        assert exc.value.status_code == 400


def test_existencias_suficientes():
    validar_existencias({1: 5, 2: 3}, {1: 5, 2: 10}, {})


def test_existencia_insuficiente_reporta_producto():
    with pytest.raises(HTTPException) as exc:
        validar_existencias({1: 6}, {1: 5}, {1: "ARMAZON X"})
    assert exc.value.status_code == 400
    assert "ARMAZON X" in exc.value.detail and "6" in exc.value.detail and "5" in exc.value.detail


def test_producto_sin_inventario_en_origen():
    with pytest.raises(HTTPException) as exc:
        validar_existencias({7: 1}, {}, {7: "LENTE Y"})
    assert "LENTE Y no esta disponible" in exc.value.detail
