"""Productos: armado del codigo por atributos y listados (una consulta de atributos para todos)."""
import pytest
from fastapi import HTTPException

from controllers import producto_controller as api
from models.atributos_model import Atributo
from models.atributos_valores_model import AtributosValores
from models.producto_model import ProductoCreate

pytestmark = pytest.mark.anyio


@pytest.fixture
async def catalogo(db):
    marca = Atributo(atributo="PRUEBA Marca", longitud=2)
    color = Atributo(atributo="PRUEBA Color", longitud=2)
    db.add_all([marca, color])
    await db.flush()
    valores = {
        "rayban": AtributosValores(atributo_id=marca.id, clave="98", descripcion="PRUEBA RayBan"),
        "oakley": AtributosValores(atributo_id=marca.id, clave="97", descripcion="PRUEBA Oakley"),
        "negro": AtributosValores(atributo_id=color.id, clave="96", descripcion="PRUEBA Negro"),
    }
    db.add_all(valores.values())
    await db.flush()
    return {"marca": marca.id, "color": color.id, **{k: v.id for k, v in valores.items()}}


def _producto(seleccion, externo="EXT-PRUEBA-ARMADO"):
    return ProductoCreate(
        atributos_seleccionados=seleccion, codigo_externo=externo, descripcion="-", tipo=1, unidad="Pieza", tipo_iva=1
    )


async def test_crea_con_valores_elegidos_y_el_menor_por_omision(db, catalogo):
    c = catalogo
    p = await api.create_product(_producto({c["marca"]: c["rayban"]}), db)
    assert "PRUEBA RayBan" in p.nombre and "98" in p.codigo
    # sin seleccion de color se usa su menor clave
    assert p.atributos_seleccionados[c["color"]] == c["negro"]

    todos = {x.id: x for x in await api.get_all_productos(db)}
    assert todos[p.id].atributos_seleccionados[c["marca"]] == c["rayban"]

    filtrados = await api.get_productos_filtrados(None, None, None, "EXT-PRUEBA-ARMADO", db)
    assert [x.atributos_seleccionados[c["marca"]] for x in filtrados] == [c["rayban"]]

    actualizado = await api.update_producto(p.id, _producto({c["marca"]: c["oakley"]}), db)
    assert "PRUEBA Oakley" in actualizado.nombre and actualizado.atributos_seleccionados[c["marca"]] == c["oakley"]


async def test_rechaza_valor_de_otro_atributo(db, catalogo):
    c = catalogo
    with pytest.raises(HTTPException) as exc:
        await api.create_product(_producto({c["marca"]: c["negro"]}, externo="EXT-PRUEBA-MAL"), db)
    assert exc.value.status_code == 404


async def test_no_elimina_producto_con_inventario(db, escenario):
    with pytest.raises(HTTPException) as exc:
        await api.delete_producto(escenario["p1"].id, db)
    assert exc.value.status_code == 400 and "inventario" in exc.value.detail
