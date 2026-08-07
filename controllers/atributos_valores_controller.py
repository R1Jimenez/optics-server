from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.database import get_db
from models.atributos_valores_model import AtributosValores, AtribValoresCreate, AtribValoresOutput, AtribValoresUpdate
from models.atributos_model import Atributo

router = APIRouter(prefix="/atributosvalores", tags=["AtributosValores"])

@router.post("/create", response_model=AtribValoresOutput)
async def create_valor(valor: AtribValoresCreate, db: AsyncSession = Depends(get_db)):

    try:
        atributo_query = select(Atributo).where(Atributo.id == valor.atributo_id)
        atributo_result = await db.execute(atributo_query)
        atributo = atributo_result.scalar_one_or_none()

        if not atributo:
            raise HTTPException(status_code=404, detail = "El atributo especificado no existe")
        
        longitud = atributo.longitud
        inicio = 1 if valor.atributo_id == 2 else 0
        max_valores = (10 ** longitud) - inicio

        count_query = select(func.count()).where(AtributosValores.atributo_id == valor.atributo_id)
        count_result = await db.execute(count_query)
        total_existentes = count_result.scalar()

        if total_existentes >= max_valores:
            raise HTTPException(
                status_code=400, 
                detail=f"Este atributo ya alcanzó el máximo de {max_valores} valores permitidos ({longitud})"
            )
        
        siguiente_clave = str(total_existentes + inicio).zfill(longitud)

        existing_desc = select(AtributosValores).where(
            AtributosValores.descripcion == valor.descripcion,
            AtributosValores.atributo_id == valor.atributo_id
        )

        desc_result = await db.execute(existing_desc)
        if desc_result.scalars().first():
            raise HTTPException(status_code=400, detail = "Esta descripcion ya existe para este atributo")
        
        new_valor = AtributosValores(
            atributo_id = valor.atributo_id,
            clave = siguiente_clave,
            descripcion = valor.descripcion
        )

        db.add(new_valor)
        await db.commit()
        await db.refresh(new_valor)
        return new_valor
    
    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        print(f"Error al crear valor: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
    
@router.get("/all", response_model=list[AtribValoresOutput])
async def get_all_valores(db: AsyncSession = Depends(get_db)):
    try:
        query = select(AtributosValores)
        result = await db.execute(query)
        valores = result.scalars().all()
        return valores
    
    except Exception as e:
        print(f"Error al obtener valores: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
    
@router.get("/by-atributo/{atributo_id}", response_model=list[AtribValoresOutput])
async def get_valores_by_atributo(atributo_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(AtributosValores).where(AtributosValores.atributo_id == atributo_id)
        result = await db.execute(query)
        valores = result.scalars().all()

        if not valores:
            raise HTTPException(status_code=404, detail="Este atributo no cuenta con valores")

        return valores
    
    except Exception as e:
        print(f"Error al obtener valores por atributo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
    
@router.post("/update/{valor_id}", response_model=AtribValoresOutput)
async def update_valor(valor_id: int, atributo_update: AtribValoresUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(AtributosValores).where(AtributosValores.id == valor_id)
        result = await db.execute(query)
        valor_result = result.scalar_one_or_none()

        if not valor_result:
            raise HTTPException(
                status_code=404,
                detail="Valor no encontrado o inexistente"
            )
        
        update_data = atributo_update.dict(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=400,
                detail="No se proporcionaron datos para actualizar"
            )
        
        if "descripcion" in update_data:
            existing_valor_query = select(AtributosValores).where(AtributosValores.descripcion == update_data.get("descripcion"), AtributosValores.id != valor_id)
            existing_valor_result = await db.execute(existing_valor_query)
            existing_valor = existing_valor_result.scalar_one_or_none()

            if existing_valor:
                raise HTTPException(
                    status_code=400,
                    detail="Esta descripcion ya existe"
                )
            
        if "clave" in update_data:
            existing_clave_query = select(AtributosValores).where(AtributosValores.clave == update_data.get("clave"), AtributosValores.id != valor_id)
            existing_clave_result = await db.execute(existing_clave_query)
            existing_clave = existing_clave_result.scalar_one_or_none()

            if existing_clave:
                raise HTTPException(
                    status_code=400,
                    detail="Esta clave ya existe"
                )
        
        for key, value in update_data.items():
            setattr(valor_result, key, value)
        
        db.add(valor_result)
        await db.commit()
        await db.refresh(valor_result)
        return valor_result
    
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar valor: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{valor_id}")
async def delete_valor(valor_id: int, db: AsyncSession = Depends(get_db)):

    try:
        # 1. Buscar el valor a eliminar
        query = select(AtributosValores).where(AtributosValores.id == valor_id)
        result = await db.execute(query)
        valor_result = result.scalar_one_or_none()

        if not valor_result:
            raise HTTPException(status_code=404, detail="Valor no encontrado o inexistente")

        atributo_id = valor_result.atributo_id

        # 2. Obtener la longitud del atributo para el zero-padding
        atributo_query = select(Atributo).where(Atributo.id == atributo_id)
        atributo_result = await db.execute(atributo_query)
        atributo = atributo_result.scalar_one_or_none()
        longitud = atributo.longitud

        # 3. Eliminar el valor
        await db.delete(valor_result)
        await db.flush()   # ejecuta el delete sin hacer commit aún

        # 4. Obtener los valores restantes del mismo atributo ordenados por clave
        restantes_query = select(AtributosValores).where(
            AtributosValores.atributo_id == atributo_id
        ).order_by(AtributosValores.clave)
        restantes_result = await db.execute(restantes_query)
        restantes = restantes_result.scalars().all()

        # 5. Reasignar claves secuencialmente
        inicio = 1 if atributo_id == 2 else 0
        for i, val in enumerate(restantes):
            val.clave = str(i + inicio).zfill(longitud)

        # 6. Confirmar todo en una sola transacción
        await db.commit()
        return {"detail": "Valor eliminado y claves reordenadas correctamente"}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar valor: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")