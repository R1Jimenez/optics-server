"""Historial de conexiones. Corre en una transaccion que se revierte (ver conftest.db)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from controllers import conexiones_controller as api
from controllers.users_controller import user_login, hash_password
from models.conexiones_model import HistorialConexion
from models.users_model import User, UserLogin

pytestmark = pytest.mark.anyio


@pytest.fixture
async def usuario(db):
    u = User(
        nombres="Ana", apellidos="Garay", usuario="prueba.conexiones", email="prueba.conexiones@example.com",
        telefono="0", Sucursal=0, sucursal_acces=[], roles=[], hashed_password=hash_password("secreta")
    )
    db.add(u)
    await db.flush()
    return u


async def _historial(db, user_id):
    result = await db.execute(
        select(HistorialConexion).where(HistorialConexion.user_id == user_id).order_by(HistorialConexion.id)
    )
    return result.scalars().all()


async def test_login_registra_entrada(db, usuario):
    await user_login(UserLogin(usuario="prueba.conexiones", password="secreta"), db)

    [c] = await _historial(db, usuario.id)
    assert (c.usuario, c.nombre, c.tipo) == ("prueba.conexiones", "Ana Garay", "Entrada")
    assert abs(c.fecha - datetime.utcnow()) < timedelta(minutes=1)


async def test_login_fallido_no_registra(db, usuario):
    with pytest.raises(HTTPException) as exc:
        await user_login(UserLogin(usuario="prueba.conexiones", password="incorrecta"), db)
    assert exc.value.status_code == 401
    assert await _historial(db, usuario.id) == []


async def test_salida_registra_al_usuario_del_token(db, usuario):
    c = await api.registrar_salida(db, {"id": usuario.id, "sub": usuario.usuario})
    assert (c.usuario, c.nombre, c.tipo) == ("prueba.conexiones", "Ana Garay", "Salida")


async def test_salida_de_usuario_inexistente(db):
    with pytest.raises(HTTPException) as exc:
        await api.registrar_salida(db, {"id": -1})
    assert exc.value.status_code == 404


async def test_listado_filtra_y_pagina(db, usuario):
    base = datetime(2026, 10, 29, 18, 0)
    db.add_all([
        HistorialConexion(user_id=usuario.id, usuario=usuario.usuario, nombre="Ana Garay", tipo=tipo, fecha=base + timedelta(minutes=m))
        for tipo, m in [("Entrada", 0), ("Salida", 30), ("Entrada", 60), ("Salida", 24 * 60)]
    ])
    await db.flush()

    todas = await api.listar_conexiones(usuario.id, None, None, None, 1, 10, db)
    assert todas.total == 4
    # mas recientes primero
    assert [c.fecha for c in todas.items] == sorted((c.fecha for c in todas.items), reverse=True)

    entradas = await api.listar_conexiones(usuario.id, "Entrada", None, None, 1, 10, db)
    assert entradas.total == 2 and {c.tipo for c in entradas.items} == {"Entrada"}

    # el dia se envia con zona horaria (medianoche local); se compara en UTC
    zona = timezone(timedelta(hours=-6))
    desde = datetime(2026, 10, 29, tzinfo=zona)
    del_dia = await api.listar_conexiones(usuario.id, None, desde, desde + timedelta(days=1), 1, 10, db)
    assert del_dia.total == 3

    pagina2 = await api.listar_conexiones(usuario.id, None, None, None, 2, 3, db)
    assert (pagina2.total, len(pagina2.items)) == (4, 1)
    assert pagina2.items[0].fecha == base
