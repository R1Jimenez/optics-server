from sqlalchemy import select, func


async def paginar(db, query, orden, pagina: int, por_pagina: int):
    """Devuelve (total, filas) de una pagina con una sola consulta usando count(*) OVER().
    Cada fila conserva las columnas originales del query (sin el total)."""
    result = await db.execute(
        query.add_columns(func.count().over().label("total_filas"))
        .order_by(*orden)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )
    filas = result.all()
    if filas:
        return filas[0][-1], [fila[:-1] for fila in filas]
    if pagina == 1:
        return 0, []
    # pagina fuera de rango: no hay filas de donde leer el total
    return await db.scalar(select(func.count()).select_from(query.subquery())), []
