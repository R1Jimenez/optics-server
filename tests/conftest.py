import os
import sys

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402,F401  registra todos los modelos
from database.database import settings  # noqa: E402
from models.sucursales_model import Sucursal  # noqa: E402
from models.users_model import User  # noqa: E402
from models.producto_model import Productos  # noqa: E402
from models.inventario_model import InventarioSucursal  # noqa: E402

# NullPool: cada prueba corre en su propio event loop y no puede reutilizar conexiones de otro
engine_pruebas = create_async_engine(settings.postgres_url, poolclass=NullPool)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db():
    """Sesion dentro de una transaccion que se revierte al final: los commits de los endpoints son savepoints."""
    async with engine_pruebas.connect() as conn:
        transaccion = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await transaccion.rollback()


@pytest.fixture
async def escenario(db):
    """Dos sucursales, un usuario y dos productos; solo el origen tiene inventario."""
    origen = Sucursal(sucursal="PRUEBA Origen", tipo_sucursal_id=1, dependencia="-", mondeda="MXN", razon_social="-", estado_sucursal_id=1)
    destino = Sucursal(sucursal="PRUEBA Destino", tipo_sucursal_id=1, dependencia="-", mondeda="MXN", razon_social="-", estado_sucursal_id=1)
    usuario = User(
        nombres="Prueba", apellidos="Traspasos", usuario="prueba.traspasos", email="prueba.traspasos@example.com",
        telefono="0", Sucursal=0, sucursal_acces=[], roles=[], hashed_password="x"
    )
    db.add_all([origen, destino, usuario])
    await db.flush()

    productos = [
        Productos(nombre=f"PRODUCTO PRUEBA {i}", codigo=f"PRUEBA{i:014d}", codigo_externo=f"EXT-PRUEBA-{i}",
                  descripcion=f"Descripcion {i}", estatus=1, tipo=1, genera_orden=0, unidad="Pieza", tipo_iva=1)
        for i in (1, 2)
    ]
    db.add_all(productos)
    await db.flush()

    db.add_all([
        InventarioSucursal(sucursal_id=origen.id, producto_id=productos[0].id, existencia_actual=10, punto_reorden=2),
        InventarioSucursal(sucursal_id=origen.id, producto_id=productos[1].id, existencia_actual=3, punto_reorden=1),
    ])
    await db.flush()

    return {
        "origen": origen,
        "destino": destino,
        "usuario": {"id": usuario.id, "sub": usuario.usuario},
        "p1": productos[0],
        "p2": productos[1],
    }
