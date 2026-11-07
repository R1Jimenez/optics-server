import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from database.database import engine, Base
from database.migraciones import aplicar_migraciones, crear_tablas_faltantes
from middleware.errores import manejar_http_exception, ManejoErrores, ReintentoLectura
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from routes import opticaroutes
from controllers import (cotizacion_controller, users_controller, estado_sucursal_controller, tipo_sucursal_controller, sucursales_controller,
                         users_roles_contoller, tipo_cliente_controller, clientes_controller, pacientes_controller,
                         armazon_controler, servicio_controller, material_controller, tipo_venta_controller,
                         plazo_controller, producto_controller, tiprod_controller,
                         marcaprod_controller, tipolente_controller, materialente_controller,
                         colorlente_controller, rangolente_controller, atributos_controller,
                         atributos_valores_controller, precios_sucursal_controller, inventario_controller,
                         exploraciones_controller, info_referencial_controller, ordenes_trabajo_controller,
                         abonos_controller, traspasos_controller, promociones_controller,
                         conexiones_controller, pagos_controller)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI()

# Crear tablas al iniciar
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(crear_tablas_faltantes, Base.metadata)
        await aplicar_migraciones(conn)

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()

app.add_exception_handler(StarletteHTTPException, manejar_http_exception)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        error_dict = {
            "loc": error.get("loc"),
            "msg": error.get("msg"),
            "type": error.get("type")
        }
        # Convertir input a string si es bytes
        if "input" in error and isinstance(error["input"], bytes):
            error_dict["input"] = error["input"].decode("utf-8")
        elif "input" in error:
            error_dict["input"] = str(error["input"])
        errors.append(error_dict)
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Datos incompletos o inválidos",
            "detalle": errors
        }
    )

# El ultimo middleware agregado queda por fuera: CORS > GZip > reintento > manejo de errores > rutas
app.add_middleware(ManejoErrores)
app.add_middleware(ReintentoLectura)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(opticaroutes.router, prefix = "/visualoptics")
app.include_router(users_controller.router)
app.include_router(estado_sucursal_controller.router)
app.include_router(tipo_sucursal_controller.router)
app.include_router(sucursales_controller.router)
app.include_router(users_roles_contoller.router)
app.include_router(tipo_cliente_controller.router)
app.include_router(clientes_controller.router)
app.include_router(pacientes_controller.router)
app.include_router(armazon_controler.router)
app.include_router(servicio_controller.router)
app.include_router(material_controller.router)
app.include_router(tipo_venta_controller.router)
app.include_router(plazo_controller.router)
app.include_router(producto_controller.router)
app.include_router(tiprod_controller.router)
app.include_router(marcaprod_controller.router)
app.include_router(cotizacion_controller.router)
app.include_router(tipolente_controller.router)
app.include_router(materialente_controller.router)
app.include_router(colorlente_controller.router)
app.include_router(rangolente_controller.router)
app.include_router(atributos_controller.router)
app.include_router(atributos_valores_controller.router)
app.include_router(precios_sucursal_controller.router)
app.include_router(inventario_controller.router)
app.include_router(exploraciones_controller.router)
app.include_router(info_referencial_controller.router)
app.include_router(ordenes_trabajo_controller.router)
app.include_router(abonos_controller.router)
app.include_router(traspasos_controller.router)
app.include_router(promociones_controller.router)
app.include_router(conexiones_controller.router)
app.include_router(pagos_controller.router)
@app.get("/")
async def root():
    return {"message": "FastAPI + PostgresSQL funcionan!"}