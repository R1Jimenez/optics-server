from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.orm import selectinload
from database.database import get_db
from models.order_model import Order, OrderCreate, OrderUpdate, OrderOut, order_productos
from models.producto_model import Productos
from models.tipo_venta_model import TipoVenta
from models.plazo_model import Plazo

router = APIRouter(prefix="/order", tags=["Orders"])

@router.post("/create", response_model=OrderOut)
async def create_order(order: OrderCreate, db: AsyncSession = Depends(get_db)):
    try:
        query_tipo_venta = select(TipoVenta).where(TipoVenta.id == order.tipo_venta_id)
        result_tipo_venta = await db.execute(query_tipo_venta)
        if not result_tipo_venta.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Tipo de venta no encontrado")
        
        query_plazo = select(Plazo).where(Plazo.id == order.plazo_id)
        result_plazo = await db.execute(query_plazo)
        if not result_plazo.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Plazo no encontrado")
        
        for item in order.productos:
            query_producto = select(Productos).where(Productos.id == item.producto_id)
            result_producto = await db.execute(query_producto)
            if not result_producto.scalar_one_or_none():
                raise HTTPException(
                    status_code=404, 
                    detail=f"Producto con ID {item.producto_id} no encontrado"
                )
        
        new_order = Order(
            tipo_venta_id=order.tipo_venta_id,
            plazo_id=order.plazo_id,
            pago_inicial=order.pago_inicial
        )
        
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        
        for item in order.productos:
            stmt = insert(order_productos).values(
                order_id=new_order.id,
                producto_id=item.producto_id,
                cantidad=item.cantidad
            )
            await db.execute(stmt)
        
        await db.commit()
        
        query = select(Order).where(Order.id == new_order.id).options(
            selectinload(Order.productos),
            selectinload(Order.tipo_venta),
            selectinload(Order.plazo)
        )
        result = await db.execute(query)
        order_with_products = result.scalar_one()
        
        return order_with_products
    
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error al crear pedido: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@router.get("/all", response_model=list[OrderOut])
async def get_all_orders(db: AsyncSession = Depends(get_db)):
    try:
        query = select(Order).options(
            selectinload(Order.productos),
            selectinload(Order.tipo_venta),
            selectinload(Order.plazo)
        )
        result = await db.execute(query)
        orders = result.scalars().all()
        return orders
    
    except Exception as e:
        print(f"Error al obtener pedidos: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Order).where(Order.id == order_id).options(
            selectinload(Order.productos),
            selectinload(Order.tipo_venta),
            selectinload(Order.plazo)
        )
        result = await db.execute(query)
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        return order
    
    except Exception as e:
        print(f"Error al obtener pedido: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")

@router.put("/update/{order_id}", response_model=OrderOut)
async def update_order(order_id: int, order_update: OrderUpdate, db: AsyncSession = Depends(get_db)):
    try:
        query = select(Order).where(Order.id == order_id).options(
            selectinload(Order.productos),
            selectinload(Order.tipo_venta),
            selectinload(Order.plazo)
        )
        result = await db.execute(query)
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        # Actualizar campos básicos
        update_data = order_update.dict(exclude_unset=True, exclude={'productos'})
        for key, value in update_data.items():
            setattr(order, key, value)
        
        # Si se actualizan los productos, eliminar los viejos y agregar los nuevos
        if order_update.productos is not None:
            # Eliminar productos existentes
            await db.execute(
                order_productos.delete().where(order_productos.c.order_id == order_id)
            )
            
            # Agregar nuevos productos
            for item in order_update.productos:
                # Validar que el producto existe
                query_producto = select(Productos).where(Productos.id == item.producto_id)
                result_producto = await db.execute(query_producto)
                if not result_producto.scalar_one_or_none():
                    raise HTTPException(
                        status_code=404,
                        detail=f"Producto con ID {item.producto_id} no encontrado"
                    )
                
                stmt = insert(order_productos).values(
                    order_id=order_id,
                    producto_id=item.producto_id,
                    cantidad=item.cantidad
                )
                await db.execute(stmt)

        await db.commit()
        await db.refresh(order)
        
        # Recargar con productos
        query = select(Order).where(Order.id == order_id).options(
            selectinload(Order.productos),
            selectinload(Order.tipo_venta),
            selectinload(Order.plazo)
        )
        result = await db.execute(query)
        order_updated = result.scalar_one()
        
        return order_updated
    
    except HTTPException:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
    
@router.delete("/delete/{order_id}")
async def delete_order(order_id: int, db: AsyncSession = Depends(get_db)):
    
    try:
        query = select(Order).where(Order.id == order_id)
        result = await db.execute(query)
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        await db.delete(order)
        await db.commit()
        return {"detail": "Pedido eliminado exitosamente"}
    
    except Exception as e:
        await db.rollback()
        print(f"Error al eliminar pedido: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )
