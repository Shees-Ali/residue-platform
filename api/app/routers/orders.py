import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_buyer, current_user
from app.auth.owners import factory_of
from app.db_models.tables import Order, Product
from app.deps import DbSession, Delivery
from app.models.market import OrderIn, OrderOut
from app.services.inbox import commit_and_deliver
from app.services.market import order_out, place_order
from app.services.notify import emit

router = APIRouter(prefix="/api/orders", tags=["orders"])
LOW_STOCK = 5  # a factory is told when a product's stock falls to this or below


def _key(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, f"Unknown {what}") from None


@router.post("", response_model=OrderOut, status_code=201)
async def post_orders_root(
    db: DbSession, inbox: Delivery, body: OrderIn, user: AuthUser = as_buyer
):
    """Place an order (payment is simulated). Reduces stock and writes the four-way split."""
    order_id = await place_order(db, user.uid, _key(body.product_id, "product"), body.quantity)
    out = await order_out(db, order_id)
    # the buyer hears it too: their receipt
    await emit(db, "order.placed", order_id=order_id, actor=user, include_actor=True)
    stock = (
        await db.execute(
            select(Product.stock).where(Product.id == _key(body.product_id, "product"))
        )
    ).scalar_one()
    if stock <= LOW_STOCK < stock + body.quantity:  # just crossed the line
        await emit(db, "product.low_stock", order_id=order_id, actor=user, stock=stock)
    await commit_and_deliver(db, inbox)
    return out


@router.get("", response_model=list[OrderOut])
async def get_orders_root(db: DbSession, user: AuthUser = Depends(current_user)):
    """A buyer's own orders, a factory's orders for its products, or all of them (admin)."""
    query = select(Order.id).order_by(Order.created_at.desc()).limit(100)
    if user.role == "buyer":
        query = query.where(Order.buyer_uid == user.uid)
    elif user.role == "factory":
        factory = await factory_of(db, user)
        query = query.join(Product, Product.id == Order.product_id).where(
            Product.factory_id == factory.id
        )
    elif user.role != "admin":
        raise HTTPException(403, "Forbidden")
    return [await order_out(db, i) for i in (await db.execute(query)).scalars().all()]


@router.get("/{order_id}/split", response_model=OrderOut)
async def get_orders_order_id_split(
    db: DbSession, order_id: str, user: AuthUser = Depends(current_user)
):
    """How the sale is divided; shares add to 10000 bps and amounts to the order total."""
    if user.role not in ("buyer", "factory", "admin"):
        raise HTTPException(403, "Forbidden")
    key = _key(order_id, "order")
    order = await db.get(Order, key)
    if order is None:
        raise HTTPException(404, "Unknown order")
    if user.role == "buyer" and order.buyer_uid != user.uid:
        raise HTTPException(404, "Unknown order")
    if user.role == "factory":
        product = await db.get(Product, order.product_id)
        if product.factory_id != (await factory_of(db, user)).id:
            raise HTTPException(404, "Unknown order")
    return await order_out(db, key)
