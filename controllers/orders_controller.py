from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload
from database.database import get_db
from models.orders_model import Orders, OrderCreate, OrderOut
from models.users_model import User
from models.clientes_model import Cliente

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/create", response_model=OrderOut)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    # Verificar que el usuario existe
    query_user = select(User).where(User.id == order.id_user)
    result_user = await db.execute(query_user)
    user = result_user.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el cliente existe
    query_cliente = select(Cliente).where(Cliente.id == order.cliente_id)
    result_cliente = await db.execute(query_cliente)
    cliente = result_cliente.scalar_one_or_none()
    
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    # Verificar que el order_id no exista ya
    query_order = select(Orders).where(Orders.order_id == order.order_id)
    result_order = await db.execute(query_order)
    existing_order = result_order.scalar_one_or_none()
    
    if existing_order:
        raise HTTPException(status_code=400, detail="El ID de orden ya existe")
    
    new_order = Orders(
        id_user=order.id_user,
        cliente_id=order.cliente_id,
        order_id=order.order_id
    )
    
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    
    return new_order

@router.get("/all", response_model=list[OrderOut])
async def list_orders(db: AsyncSession = Depends(get_db)):
    query = select(Orders)
    result = await db.execute(query)
    orders = result.scalars().all()
    
    return orders

@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Orders).where(Orders.id == order_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order

@router.put("/update/{order_id}", response_model=OrderOut)
async def update_order(order_id: int, order_update: OrderCreate, db: AsyncSession = Depends(get_db)):
    query = select(Orders).where(Orders.id == order_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.id_user = order_update.id_user
    order.cliente_id = order_update.cliente_id
    order.order_id = order_update.order_id
    
    db.add(order)
    await db.commit()
    await db.refresh(order)
    
    return order

@router.delete("/delete/{order_id}")
async def delete_order(order_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Orders).where(Orders.id == order_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    await db.delete(order)
    await db.commit()
    
    return {"detail": "Order deleted successfully"}