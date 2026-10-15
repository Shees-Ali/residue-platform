"""Lots as the dashboards see them: the lot, its farmer, the matched factory and the quote."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, Farmer, Job, Lot, ResidueType
from app.models.lot import LotOut
from app.services.economics import gross, job_shares, payouts


def lot_query():
    return (
        select(Lot, Job, Farmer, ResidueType.label, Factory.name)
        .join(Farmer, Farmer.id == Lot.farmer_id)
        .join(ResidueType, ResidueType.code == Lot.residue_code)
        .outerjoin(Job, Job.lot_id == Lot.id)
        .outerjoin(Factory, Factory.id == Job.factory_id)
    )


def lot_out(row) -> LotOut:
    lot, job, farmer, residue_label, factory_name = row
    payout = None
    if job is not None:
        shares = job_shares(job.farmer_share_bps)
        payout = payouts(gross(job.est_weight_kg, job.quoted_price_per_tonne), shares)["farmer"]
    return LotOut(
        id=str(lot.id),
        farmer_id=str(lot.farmer_id),
        farmer_name=farmer.name or None,
        farmer_phone=farmer.phone,
        residue_type=lot.residue_code,
        residue_label=residue_label,
        quantity_tonnes=float(lot.quantity_tonnes),
        village=lot.village_name,
        district=lot.district,
        place_match=lot.place_match,
        lat=lot.lat,
        lon=lot.lon,
        status=lot.status,
        factory_name=factory_name,
        quoted_price_per_tonne=job.quoted_price_per_tonne if job else None,
        farmer_share_bps=job.farmer_share_bps if job else None,
        est_farmer_payout=payout,
        pickup_from=lot.pickup_from,
        pickup_to=lot.pickup_to,
        job_id=str(job.id) if job else None,
        job_state=job.state if job else None,
        created_at=lot.created_at,
    )


async def get_lot_out(db: AsyncSession, lot_id: uuid.UUID) -> LotOut | None:
    row = (await db.execute(lot_query().where(Lot.id == lot_id))).first()
    return lot_out(row) if row else None
