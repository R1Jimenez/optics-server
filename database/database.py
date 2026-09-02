from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings

class Settings (BaseSettings):
    postgres_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    class Config:
        env_file = ".env"

settings = Settings()

engine = create_async_engine(
    settings.postgres_url,
    echo=True
)

SessionLocal = sessionmaker (
    bind = engine,
    class_=AsyncSession,
    expire_on_commit = False
)

Base = declarative_base()

async def get_db ():
    async with SessionLocal() as session:
        yield session