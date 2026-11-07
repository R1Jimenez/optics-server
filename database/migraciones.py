from sqlalchemy import inspect

# create_all no altera tablas existentes: columnas agregadas a tablas que ya estaban creadas.
# Deben ser idempotentes porque se ejecutan en cada arranque.
MIGRACIONES = [
    "ALTER TABLE inventario_movimiento ADD COLUMN IF NOT EXISTS tipo VARCHAR(60)",
    "ALTER TABLE inventario_movimiento ADD COLUMN IF NOT EXISTS referencia VARCHAR(100)",
    "ALTER TABLE inventario_movimiento ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES users(id)",
    'ALTER TABLE "Cotizaciones" ADD COLUMN IF NOT EXISTS promocion_id INTEGER REFERENCES promociones(id)',
    'ALTER TABLE "CotizacionDetalle" ADD COLUMN IF NOT EXISTS descuento_porcentaje NUMERIC(5, 2)',
    'ALTER TABLE "Cotizaciones" ADD COLUMN IF NOT EXISTS pago_inicial_pago_id INTEGER REFERENCES pagos(id)',
    'CREATE INDEX IF NOT EXISTS "ix_Cotizaciones_pago_inicial_pago_id" ON "Cotizaciones" (pago_inicial_pago_id)',
    "ALTER TABLE abonos ADD COLUMN IF NOT EXISTS pago_id INTEGER REFERENCES pagos(id)",
    "CREATE INDEX IF NOT EXISTS ix_abonos_pago_id ON abonos (pago_id)",
    "ALTER TABLE tipo_venta ADD COLUMN IF NOT EXISTS es_credito BOOLEAN",
    # solo clasifica los tipos que aun no tienen valor, para respetar cambios posteriores
    "UPDATE tipo_venta SET es_credito = (lower(venta) LIKE 'cr_dito%') WHERE es_credito IS NULL",
    "ALTER TABLE tipo_venta ALTER COLUMN es_credito SET DEFAULT false",
    "ALTER TABLE tipo_venta ALTER COLUMN es_credito SET NOT NULL",
    # indices para las busquedas mas frecuentes (por cliente, sucursal, producto o venta)
    'CREATE INDEX IF NOT EXISTS "ix_Cotizaciones_id_cliente" ON "Cotizaciones" (id_cliente)',
    'CREATE INDEX IF NOT EXISTS "ix_Cotizaciones_sucursal_fecha" ON "Cotizaciones" (sucursal_id, fecha)',
    'CREATE INDEX IF NOT EXISTS "ix_CotizacionDetalle_cotizacion_id" ON "CotizacionDetalle" (cotizacion_id)',
    "CREATE INDEX IF NOT EXISTS ix_producto_atributos_producto_id ON producto_atributos (producto_id)",
    "CREATE INDEX IF NOT EXISTS ix_inventario_movimiento_inventario_id ON inventario_movimiento (inventario_id)",
    "CREATE INDEX IF NOT EXISTS ix_inventario_movimiento_fecha ON inventario_movimiento (fecha)",
    "CREATE INDEX IF NOT EXISTS ix_pacientes_cliente_id ON pacientes (cliente_id)",
    "CREATE INDEX IF NOT EXISTS ix_exploraciones_paciente_id ON exploraciones (paciente_id)",
    "CREATE INDEX IF NOT EXISTS ix_info_referencial_paciente_id ON info_referencial (paciente_id)",
    "CREATE INDEX IF NOT EXISTS ix_ordenes_trabajo_sucursal_id ON ordenes_trabajo (sucursal_id)",
    'ALTER TABLE "Cotizaciones" ADD COLUMN IF NOT EXISTS liquidacion_impresa BOOLEAN NOT NULL DEFAULT false',
]


async def aplicar_migraciones(conn):
    # se envian juntas en una sola ida y vuelta al servidor (asyncpg admite varias sentencias sin parametros)
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(";\n".join(MIGRACIONES))


def crear_tablas_faltantes(sync_conn, metadata):
    """Como create_all, pero consulta el catalogo una sola vez en lugar de una vez por tabla."""
    existentes = set(inspect(sync_conn).get_table_names())
    faltantes = [t for t in metadata.sorted_tables if t.name not in existentes]
    if faltantes:
        metadata.create_all(sync_conn, tables=faltantes, checkfirst=False)
