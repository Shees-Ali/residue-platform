"""FA3/B1: product listings and orders. Stock is decremented atomically in SQL."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Order, Product, SaleSplit
from app.models.market import OrderOut, SplitLine
from app.services.economics import sale_shares
from app.services.job_flow import add_ledger
from app.services.revenue_share import split

# How each party of a sale is recorded in the ledger
SALE_KIND = {
    "farmer": "release_farmer",
    "factory": "release_factory",
    "ngo": "release_ngo",
    "platform": "platform_fee",
}


async def place_order(
    db: AsyncSession, buyer_uid: str, product_id: uuid.UUID, quantity: int
) -> uuid.UUID:
    """Buy `quantity` of a product. Payment is simulated, so the order is paid straight away.

    The conditional UPDATE is what stops two buyers taking the last unit: one matches, one fails.
    """
    bought = (
        await db.execute(
            update(Product)
            .where(Product.id == product_id, Product.active, Product.stock >= quantity)
            .values(stock=Product.stock - quantity)
            .returning(Product.unit_price)
        )
    ).first()
    if bought is None:
        exists = (await db.execute(select(Product.id).where(Product.id == product_id))).first()
        if exists is None:
            raise HTTPException(404, "Unknown product")
        raise HTTPException(409, "Not enough stock, or the product is not for sale")
    total = bought[0] * quantity
    order = Order(
        buyer_uid=buyer_uid, product_id=product_id, quantity=quantity, total=total, status="paid"
    )
    db.add(order)
    await db.flush()

    shares = sale_shares()
    amounts = split(total, shares)
    await add_ledger(db, None, "escrow_in", total, buyer_uid, order_id=order.id)
    for party, bps in shares.items():
        db.add(SaleSplit(order_id=order.id, party=party, share_bps=bps, amount=amounts[party]))
        await add_ledger(db, None, SALE_KIND[party], amounts[party], None, order_id=order.id)
    await db.flush()
    return order.id


async def order_out(db: AsyncSession, order_id: uuid.UUID) -> OrderOut:
    order = await db.get(Order, order_id)
    rows = (
        await db.execute(select(SaleSplit).where(SaleSplit.order_id == order_id))
    ).scalars().all()
    parties = list(SALE_KIND)
    rows = sorted(rows, key=lambda r: parties.index(r.party))
    return OrderOut(
        id=str(order.id),
        product_id=str(order.product_id),
        quantity=order.quantity,
        total=order.total,
        status=order.status,
        splits=[SplitLine(party=r.party, share_bps=r.share_bps, amount=r.amount) for r in rows],
        shares_total_bps=sum(r.share_bps for r in rows),
        amounts_total=sum(r.amount for r in rows),
    )
