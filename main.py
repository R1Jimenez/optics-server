from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from database.database import engine, Base
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from routes import opticaroutes
from controllers import (users_controller, estado_sucursal_controller, tipo_sucursal_controller, sucursales_controller,
                         users_roles_contoller, tipo_cliente_controller, clientes_controller, pacientes_controller,
                         armazon_controler, servicio_controller, material_controller, tipo_venta_controller,
                         plazo_controller, producto_controller, order_controller, orders_controller, tiprod_controller,
                         marcaprod_controller, modeloprod_controller, tipolente_controller, materialente_controller,
                         colorlente_controller, rangolente_controller, ordenproducto_controller, atributos_controller,
                         atributos_valores_controller, precios_sucursal_controller)

app = FastAPI()

# Crear tablas al iniciar
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
app.include_router(order_controller.router)
app.include_router(orders_controller.router)
app.include_router(tiprod_controller.router)
app.include_router(marcaprod_controller.router)
app.include_router(modeloprod_controller.router)
app.include_router(tipolente_controller.router)
app.include_router(materialente_controller.router)
app.include_router(colorlente_controller.router)
app.include_router(rangolente_controller.router)
app.include_router(ordenproducto_controller.router)
app.include_router(atributos_controller.router)
app.include_router(atributos_valores_controller.router)
app.include_router(precios_sucursal_controller.router)
@app.get("/")
async def root():
    return {"message": "FastAPI + PostgresSQL funcionan!"}