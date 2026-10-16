"""F2: what the agent tells the farmer. Same economics functions as settlement, so they agree."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Job, Lot
from app.models.quote import QuoteOut
from app.services.economics import gross, job_shares, payouts
from app.services.lots import LotError

PAYMENT_TIMING = (
    "You are paid after the factory weighs and confirms the lot, and you confirm the weight "
    "and amount by phone."
)


def rupees(paisa: int) -> float:
    return round(paisa / 100, 2)


async def quote_for(
    db: AsyncSession, farmer_id: uuid.UUID, lot_id: str, *, only_call: uuid.UUID | None = None
) -> QuoteOut:
    """Quote for one of this farmer's lots. A lot that isn't theirs looks like an unknown lot.
    `only_call` (an unverified /phone call, F5) also hides lots made on any other call."""
    try:
        lot_key = uuid.UUID(lot_id)
    except ValueError:
        raise LotError("unknown_lot", "No such lot") from None
    query = select(Lot).where(Lot.id == lot_key, Lot.farmer_id == farmer_id)
    if only_call is not None:
        query = query.where(Lot.call_id == only_call)
    lot = (await db.execute(query)).scalar_one_or_none()
    if lot is None:
        raise LotError("unknown_lot", "No such lot")
    job = (await db.execute(select(Job).where(Job.lot_id == lot.id))).scalar_one_or_none()
    if job is None:
        raise LotError(
            "no_factory_yet", "No factory accepts this lot yet, so there is no price to quote"
        )
    shares = job_shares(job.farmer_share_bps)
    estimate = gross(job.est_weight_kg, job.quoted_price_per_tonne)
    parts = payouts(estimate, shares)
    return QuoteOut(
        lot_id=str(lot.id),
        price_per_tonne=job.quoted_price_per_tonne,
        price_per_tonne_rupees=rupees(job.quoted_price_per_tonne),
        farmer_share_bps=shares.farmer_bps,
        farmer_share_percent=shares.farmer_bps / 100,
        farmer_per_tonne_rupees=rupees(
            payouts(job.quoted_price_per_tonne, shares)["farmer"]
        ),
        est_weight_kg=job.est_weight_kg,
        est_total=estimate,
        est_farmer_amount=parts["farmer"],
        est_farmer_amount_rupees=rupees(parts["farmer"]),
        payment_timing=PAYMENT_TIMING,
    )

