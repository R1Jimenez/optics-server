"""Manejo central de errores: respuestas uniformes, sin exponer detalles internos, y reintento ante desconexiones."""
import asyncio
import logging

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from sqlalchemy import exc as sa_exc
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("optica.errores")

ENCABEZADO_REINTENTABLE = "x-db-reintentable"
MENSAJE_INTERNO = "Error interno del servidor"
MENSAJE_BD = "No se pudo comunicar con la base de datos. Intente de nuevo en unos segundos."


def _cadena(error: BaseException | None):
    """Recorre la excepcion y sus causas (raise ... from / except ... raise)."""
    vistos = set()
    while error is not None and id(error) not in vistos:
        vistos.add(id(error))
        yield error
        error = error.__cause__ or error.__context__


def es_desconexion(error: BaseException | None) -> bool:
    for e in _cadena(error):
        if isinstance(e, sa_exc.DBAPIError) and e.connection_invalidated:
            return True
        if isinstance(e, (sa_exc.DisconnectionError, sa_exc.TimeoutError, ConnectionError, asyncio.TimeoutError, TimeoutError)):
            return True
        # asyncpg: InterfaceError("connection is closed"), ConnectionDoesNotExistError, CannotConnectNowError...
        if type(e).__module__.startswith("asyncpg") and type(e).__name__ in {
            "InterfaceError", "ConnectionDoesNotExistError", "CannotConnectNowError",
            "ConnectionFailureError", "TooManyConnectionsError",
        }:
            return True
    return False


def _error_cliente_original(error: BaseException | None) -> StarletteHTTPException | None:
    # muchos endpoints envuelven cualquier excepcion (incluso un 404 propio) en un 500 generico
    for e in _cadena(error):
        if isinstance(e, StarletteHTTPException) and e.status_code < 500:
            return e
    return None


def respuesta_bd_no_disponible() -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": MENSAJE_BD}, headers={ENCABEZADO_REINTENTABLE: "1"})


async def manejar_http_exception(request: Request, exc: StarletteHTTPException):
    if exc.status_code < 500:
        return await http_exception_handler(request, exc)

    original = _error_cliente_original(exc.__context__)
    if original is not None:
        return await http_exception_handler(request, original)
    if es_desconexion(exc):
        logger.warning("Base de datos no disponible en %s %s", request.method, request.url.path)
        return respuesta_bd_no_disponible()

    causa = exc.__cause__ or exc.__context__
    logger.error(
        "Error %s en %s %s: %s", exc.status_code, request.method, request.url.path, exc.detail,
        exc_info=(type(causa), causa, causa.__traceback__) if causa else None,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": MENSAJE_INTERNO})


class ManejoErrores:
    """Convierte excepciones no controladas en JSON. Va dentro de CORS para que el navegador pueda leer la respuesta."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        respuesta_iniciada = False

        async def send_marcando(mensaje):
            nonlocal respuesta_iniciada
            if mensaje["type"] == "http.response.start":
                respuesta_iniciada = True
            await send(mensaje)

        try:
            await self.app(scope, receive, send_marcando)
        except Exception as e:
            if respuesta_iniciada:
                raise
            if es_desconexion(e):
                logger.warning("Base de datos no disponible en %s %s", scope["method"], scope["path"])
                respuesta = respuesta_bd_no_disponible()
            else:
                logger.exception("Error no controlado en %s %s", scope["method"], scope["path"])
                respuesta = JSONResponse(status_code=500, content={"detail": MENSAJE_INTERNO})
            await respuesta(scope, receive, send)


class ReintentoLectura:
    """Repite una sola vez las consultas (GET) que fallaron porque se perdio la conexion con la base.
    El pool ya descarto la conexion caida, asi que el reintento usa una nueva."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("GET", "HEAD"):
            return await self.app(scope, receive, send)

        primer_mensaje = None

        async def receive_repetible():
            nonlocal primer_mensaje
            if primer_mensaje is None:
                primer_mensaje = await receive()
            return primer_mensaje

        for intento in (1, 2):
            mensajes = []

            async def capturar(mensaje):
                mensajes.append(mensaje)

            await self.app(scope, receive_repetible, capturar)
            inicio = mensajes[0] if mensajes else None
            reintentable = (
                intento == 1 and inicio is not None and inicio.get("status") == 503
                and any(k.lower() == ENCABEZADO_REINTENTABLE.encode() for k, _ in inicio.get("headers", []))
            )
            if not reintentable:
                break
            logger.info("Reintentando %s tras perder la conexion con la base de datos", scope["path"])

        for mensaje in mensajes:
            await send(mensaje)
