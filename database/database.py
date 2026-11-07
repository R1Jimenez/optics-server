import time
from fastapi import Request
from sqlalchemy import event, exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings

class Settings (BaseSettings):
    postgres_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    # registrar cada SQL en consola es muy lento; activarlo solo para depurar
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # segundos que una conexion puede estar ociosa antes de verificarla al reutilizarla
    db_verificar_tras: int = 60

    class Config:
        env_file = ".env"

settings = Settings()

engine = create_async_engine(
    settings.postgres_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=15,
    pool_recycle=1800,
    # falla rapido si la base no responde en lugar de dejar la peticion colgada
    connect_args={"timeout": 10, "command_timeout": 30},
)


# Neon cierra las conexiones inactivas. Verificar en cada peticion (pool_pre_ping) cuesta un viaje
# extra a la base; solo se verifican las que estuvieron ociosas y, si fallan, el pool abre otra.
@event.listens_for(engine.sync_engine, "connect")
@event.listens_for(engine.sync_engine, "checkin")
def _marcar_uso(dbapi_connection, connection_record):
    connection_record.info["ultimo_uso"] = time.monotonic()


@event.listens_for(engine.sync_engine, "checkout")
def _verificar_conexion_ociosa(dbapi_connection, connection_record, connection_proxy):
    ultimo_uso = connection_record.info.get("ultimo_uso")
    if ultimo_uso is None or time.monotonic() - ultimo_uso < settings.db_verificar_tras:
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except Exception as e:
        raise exc.DisconnectionError("Conexion cerrada por el servidor") from e

SessionLocal = sessionmaker (
    bind = engine,
    class_=AsyncSession,
    expire_on_commit = False
)

# Las consultas (GET) no necesitan BEGIN/ROLLBACK: en autocommit cada lectura es un solo viaje a la base.
# Con READ COMMITTED (el nivel por defecto) cada sentencia ya ve su propia foto de los datos.
SessionLectura = sessionmaker(
    bind=engine.execution_options(isolation_level="AUTOCOMMIT"),
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db (request: Request):
    fabrica = SessionLectura if request.method in ("GET", "HEAD") else SessionLocal
    async with fabrica() as session:
        yield session