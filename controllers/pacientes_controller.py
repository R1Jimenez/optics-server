from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import get_db
from middleware.auth import get_current_user
from models.pacientes_model import Paciente, PacienteCreate, PacienteUpdate, PacienteOut

router = APIRouter(prefix="/pacientes", tags=["Pacientes"], dependencies=[Depends(get_current_user)])
@router.post("/create", response_model=PacienteOut)
async def create_paciente(paciente: PacienteCreate, db: AsyncSession = Depends(get_db)):

    try:
        # Verificar si el paciente ya existe SOLO dentro del mismo cliente
        query = select(Paciente).where(
            Paciente.nombres == paciente.nombres,
            Paciente.apellidos == paciente.apellidos,
            Paciente.cliente_id == paciente.cliente_id
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un paciente con el mismo nombre y apellidos para este cliente"
            )
        
        new_paciente = Paciente(
            nombres = paciente.nombres,
            apellidos = paciente.apellidos,
            edad = paciente.edad,
            ocupacion = paciente.ocupacion,
            problema_ocular = paciente.problema_ocular,
            medicamento_actual = paciente.medicamento_actual,
            lentes = paciente.lentes,
            antecedentes_familiares_lentes = paciente.antecedentes_familiares_lentes,
            hipertension = paciente.hipertension,
            diabetico = paciente.diabetico,
            util_lentes = paciente.util_lentes,
            cefaleas = paciente.cefaleas,
            princip_defi_visual = paciente.princip_defi_visual,
            otros = paciente.otros,
            cliente_id = paciente.cliente_id
        )

        db.add(new_paciente)
        await db.commit()
        await db.refresh(new_paciente)
        return new_paciente
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear paciente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.get("/all", response_model=list[PacienteOut])
async def get_all_pacientes(db: AsyncSession = Depends(get_db)):

    try:
        query = select(Paciente)
        result= await db.execute(query)
        pacientes = result.scalars().all()
        return pacientes
    
    except Exception as e:
        print(f"Error al obtener pacientes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@router.get("/cliente/{cliente_id}", response_model=list[PacienteOut])
async def get_pacientes_by_cliente(cliente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Paciente).where(Paciente.cliente_id == cliente_id)
        result = await db.execute(query)
        pacientes = result.scalars().all()
        return pacientes
    
    except Exception as e:
        print(f"Error al obtener pacientes del cliente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@router.get("/{paciente_id}", response_model=PacienteOut)
async def get_paciente(paciente_id: int, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Paciente).where(Paciente.id == paciente_id)
        result = await db.execute(query)
        paciente = result.scalar_one_or_none()

        if not paciente:
            raise HTTPException(
                status_code=404,
                detail="Paciente no encontrado"
            )
        
        return paciente
    
    except Exception as e:
        print(f"Error al obtener paciente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    

@router.post("/update/{paciente_id}", response_model=PacienteOut)
async def update_paciente(paciente_id: int, paciente_update: PacienteUpdate, db: AsyncSession = Depends(get_db)):

    try:
        query = select(Paciente).where(Paciente.id == paciente_id)
        result = await db.execute(query)
        paciente = result.scalar_one_or_none()

        if not paciente:
            raise HTTPException(
                status_code=404,
                detail="Paciente no encontrado"
            )
        
        # Actualizar los campos del paciente
        paciente.nombres = paciente_update.nombres
        paciente.apellidos = paciente_update.apellidos
        paciente.edad = paciente_update.edad
        paciente.ocupacion = paciente_update.ocupacion
        paciente.problema_ocular = paciente_update.problema_ocular
        paciente.medicamento_actual = paciente_update.medicamento_actual
        paciente.lentes = paciente_update.lentes
        paciente.antecedentes_familiares_lentes = paciente_update.antecedentes_familiares_lentes
        paciente.hipertension = paciente_update.hipertension
        paciente.diabetico = paciente_update.diabetico
        paciente.util_lentes = paciente_update.util_lentes
        paciente.cefaleas = paciente_update.cefaleas
        paciente.princip_defi_visual = paciente_update.princip_defi_visual
        paciente.otros = paciente_update.otros

        db.add(paciente)
        await db.commit()
        await db.refresh(paciente)
        return paciente
    
    except Exception as e:
        await db.rollback()
        print(f"Error al actualizar paciente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{paciente_id}")
async def delete_paciente(paciente_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Paciente).where(Paciente.id == paciente_id)
        result = await db.execute(query)
        paciente = result.scalar_one_or_none()

        if not paciente:
            raise HTTPException(
                status_code=404,
                detail="Paciente no encontrado"
            )
        
        await db.delete(paciente)
        await db.commit()
        return {"message": "Paciente eliminado correctamente"}
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar paciente: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )