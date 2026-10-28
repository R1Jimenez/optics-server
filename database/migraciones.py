from sqlalchemy import text

# create_all no altera tablas existentes: columnas agregadas a tablas que ya estaban creadas.
# Deben ser idempotentes porque se ejecutan en cada arranque.
MIGRACIONES = [
    "ALTER TABLE inventario_movimiento ADD COLUMN IF NOT EXISTS tipo VARCHAR(60)",
    "ALTER TABLE inventario_movimiento ADD COLUMN IF NOT EXISTS referencia VARCHAR(100)",
    "ALTER TABLE inventario_movimiento ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES users(id)",
    'ALTER TABLE "Cotizaciones" ADD COLUMN IF NOT EXISTS promocion_id INTEGER REFERENCES promociones(id)',
    'ALTER TABLE "CotizacionDetalle" ADD COLUMN IF NOT EXISTS descuento_porcentaje NUMERIC(5, 2)',
]


async def aplicar_migraciones(conn):
    for sentencia in MIGRACIONES:
        await conn.execute(text(sentencia))
