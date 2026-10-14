"""Read model for jobs: one query that joins everything a dashboard row needs."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, Job, Lot, Offer, Village
from app.models.job import JobOut


def _query():
    offers = (
        select(func.count()).select_from(Offer).where(Offer.job_id == Job.id).scalar_subquery()
    )
    return (
        select(Job, Factory.name, Lot.residue_code, Lot.quantity_tonnes, Village.name, offers)
        .join(Factory, Factory.id == Job.factory_id)
        .join(Lot, Lot.id == Job.lot_id)
        .outerjoin(Village, Village.id == Lot.village_id)
    )


def _out(row) -> JobOut:
    job, factory_name, residue, tonnes, village, offer_count = row
    return JobOut(
        id=str(job.id),
        lot_id=str(job.lot_id),
        factory_id=str(job.factory_id),
        factory_name=factory_name,
        transporter_id=str(job.transporter_id) if job.transporter_id else None,
        state=job.state,
        residue_type=residue,
        quantity_tonnes=float(tonnes),
        village=village,
        quoted_price_per_tonne=job.quoted_price_per_tonne,
        farmer_share_bps=job.farmer_share_bps,
        est_weight_kg=job.est_weight_kg,
        final_weight_kg=job.final_weight_kg,
        rejection_reason=job.rejection_reason,
        # funded again after offers were made means every transporter passed: needs a person
        offers_exhausted=job.state == "funded" and offer_count > 0,
        funded_at=job.funded_at,
        accepted_at=job.accepted_at,
        picked_up_at=job.picked_up_at,
        delivered_at=job.delivered_at,
        confirmed_at=job.confirmed_at,
        verified_at=job.verified_at,
        settled_at=job.settled_at,
        created_at=job.created_at,
    )


async def job_out(db: AsyncSession, job_id: uuid.UUID) -> JobOut | None:
    row = (await db.execute(_query().where(Job.id == job_id))).first()
    return _out(row) if row else None


async def list_jobs(
    db: AsyncSession,
    *,
    factory_id: uuid.UUID | None = None,
    transporter_id: uuid.UUID | None = None,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JobOut]:
    query = _query()
    if factory_id:
        query = query.where(Job.factory_id == factory_id)
    if transporter_id:
        query = query.where(Job.transporter_id == transporter_id)
    if state:
        query = query.where(Job.state == state)
    rows = (
        await db.execute(query.order_by(Job.created_at.desc()).limit(limit).offset(offset))
    ).all()
    return [_out(r) for r in rows]
