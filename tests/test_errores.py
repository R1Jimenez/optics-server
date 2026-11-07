"""Manejo central de errores (middleware/errores.py) con una app minima configurada igual que main.py."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import exc as sa_exc
from starlette.exceptions import HTTPException as StarletteHTTPException

import main
from middleware.errores import manejar_http_exception, ManejoErrores, ReintentoLectura, MENSAJE_INTERNO, MENSAJE_BD


def _desconexion():
    return sa_exc.DBAPIError("SELECT 1", None, Exception("connection is closed"), connection_invalidated=True)


def _app():
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, manejar_http_exception)
    app.add_middleware(ManejoErrores)
    app.add_middleware(ReintentoLectura)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    llamadas = {"lectura": 0, "escritura": 0}

    @app.get("/no-encontrado")
    async def no_encontrado():
        try:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

    @app.get("/fuga")
    async def fuga():
        try:
            raise ValueError('SELECT * FROM "Cotizaciones" WHERE secreto')
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

    @app.get("/lectura")
    async def lectura():
        llamadas["lectura"] += 1
        if llamadas["lectura"] == 1:
            try:
                raise _desconexion()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        return {"ok": True}

    @app.post("/escritura")
    async def escritura():
        llamadas["escritura"] += 1
        raise _desconexion()

    @app.get("/no-controlado")
    async def no_controlado():
        raise RuntimeError("detalle interno")

    return app, llamadas


def test_un_404_envuelto_en_500_conserva_su_estado():
    cliente = TestClient(_app()[0])
    r = cliente.get("/no-encontrado")
    assert (r.status_code, r.json()) == (404, {"detail": "Cliente no encontrado"})


def test_no_expone_detalles_internos():
    cliente = TestClient(_app()[0])
    r = cliente.get("/fuga")
    assert (r.status_code, r.json()) == (500, {"detail": MENSAJE_INTERNO})


def test_reintenta_una_vez_las_lecturas_si_se_pierde_la_conexion():
    app, llamadas = _app()
    r = TestClient(app).get("/lectura")
    assert (r.status_code, r.json(), llamadas["lectura"]) == (200, {"ok": True}, 2)


def test_no_reintenta_escrituras():
    app, llamadas = _app()
    r = TestClient(app, raise_server_exceptions=False).post("/escritura")
    assert (r.status_code, r.json()["detail"], llamadas["escritura"]) == (503, MENSAJE_BD, 1)


def test_error_no_controlado_responde_json_con_cors():
    cliente = TestClient(_app()[0], raise_server_exceptions=False)
    r = cliente.get("/no-controlado", headers={"Origin": "http://localhost:5173"})
    assert (r.status_code, r.json()) == (500, {"detail": MENSAJE_INTERNO})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_main_registra_la_misma_configuracion():
    capas = [m.cls.__name__ for m in main.app.user_middleware]
    assert capas == ["CORSMiddleware", "GZipMiddleware", "ReintentoLectura", "ManejoErrores"]
    assert main.app.exception_handlers[StarletteHTTPException] is manejar_http_exception
