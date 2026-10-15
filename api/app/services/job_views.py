"""Read model for jobs: one query that joins everything a dashboard row needs."""
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db_models.tables import Factory, Farmer, Job, Lot, Offer, Photo, Transporter, User
from app.models.job import JobOfferOut, JobOut, PhotoOut
from app.services.economics import gross, job_shares, payouts
from app.services.storage import get_storage


@dataclass(frozen=True)
class Viewer:
    """Who is looking, so contact details are shown only to those who need them."""

    role: str
    transporter_id: uuid.UUID | None = None


def _query():
    offers = (
        select(func.count()).select_from(Offer).where(Offer.job_id == Job.id).scalar_subquery()
    )
    carrier = aliased(User)
    return (
        select(Job, Factory, Lot, offers, Farmer, carrier.display_name)
        .join(Factory, Factory.id == Job.factory_id)
        .join(Lot, Lot.id == Job.lot_id)
        .join(Farmer, Farmer.id == Lot.farmer_id)
        .outerjoin(Transporter, Transporter.id == Job.transporter_id)
        .outerjoin(carrier, carrier.uid == Transporter.user_uid)
    )


def _out(row, viewer: Viewer | None) -> JobOut:
    job, factory, lot, offer_count, farmer, carrier_name = row
    # the farmer's phone goes to the admin, and to the transporter once the job is theirs
    reveal = viewer is not None and (
        viewer.role == "admin"
        or (viewer.role == "transporter" and job.transporter_id == viewer.transporter_id)
    )
    weight = job.final_weight_kg or job.est_weight_kg
    parts = payouts(gross(weight, job.quoted_price_per_tonne), job_shares(job.farmer_share_bps))
    return JobOut(
        id=str(job.id),
        lot_id=str(job.lot_id),
        factory_id=str(job.factory_id),
        factory_name=factory.name,
        transporter_id=str(job.transporter_id) if job.transporter_id else None,
        transporter_name=carrier_name or None,
        state=job.state,
        residue_type=lot.residue_code,
        quantity_tonnes=float(lot.quantity_tonnes),
        village=lot.village_name,
        district=lot.district,
        pickup_lat=lot.lat,
        pickup_lon=lot.lon,
        factory_lat=factory.lat,
        factory_lon=factory.lon,
        farmer_name=(farmer.name or None) if reveal else None,
        farmer_phone=farmer.phone if reveal else None,
        quoted_price_per_tonne=job.quoted_price_per_tonne,
        farmer_share_bps=job.farmer_share_bps,
        est_weight_kg=job.est_weight_kg,
        final_weight_kg=job.final_weight_kg,
        escrow_amount=gross(job.est_weight_kg, job.quoted_price_per_tonne),
        est_farmer_payout=parts["farmer"],
        est_transporter_payout=parts["transporter"],
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


async def _with_photos(db: AsyncSession, outs: list[JobOut]) -> list[JobOut]:
    """Attach each job's photos, with a URL the browser can load."""
    if not outs:
        return outs
    ids = [uuid.UUID(o.id) for o in outs]
    rows = (
        await db.execute(
            select(Photo).where(Photo.job_id.in_(ids)).order_by(Photo.created_at)
        )
    ).scalars().all()
    storage = get_storage()
    by_job: dict[str, list[PhotoOut]] = {}
    for p in rows:
        by_job.setdefault(str(p.job_id), []).append(
            PhotoOut(
                id=str(p.id),
                kind=p.kind,
                weight_kg=p.weight_kg,
                url=await storage.read_url(p.storage_path),
                created_at=p.created_at,
            )
        )
    for o in outs:
        o.photos = by_job.get(o.id, [])
    return outs


async def job_out(
    db: AsyncSession, job_id: uuid.UUID, viewer: Viewer | None = None
) -> JobOut | None:
    row = (await db.execute(_query().where(Job.id == job_id))).first()
    return (await _with_photos(db, [_out(row, viewer)]))[0] if row else None


async def list_jobs(
    db: AsyncSession,
    *,
    factory_id: uuid.UUID | None = None,
    transporter_id: uuid.UUID | None = None,
    farmer_uid: str | None = None,
    state: str | None = None,
    viewer: Viewer | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[JobOut]:
    query = _query()
    if factory_id:
        query = query.where(Job.factory_id == factory_id)
    if transporter_id:
        query = query.where(Job.transporter_id == transporter_id)
    if farmer_uid:
        query = query.where(Farmer.user_uid == farmer_uid)
    if state:
        query = query.where(Job.state == state)
    rows = (
        await db.execute(query.order_by(Job.created_at.desc()).limit(limit).offset(offset))
    ).all()
    return await _with_photos(db, [_out(r, viewer) for r in rows])


async def job_ladder(db: AsyncSession, job_id: uuid.UUID) -> list[JobOfferOut]:
    """Every offer made for a job, in order, with who got it (admin view)."""
    rows = (
        await db.execute(
            select(Offer, User.display_name, Transporter.phone)
            .join(Transporter, Transporter.id == Offer.transporter_id)
            .outerjoin(User, User.uid == Transporter.user_uid)
            .where(Offer.job_id == job_id)
            .order_by(Offer.sequence)
        )
    ).all()
    return [
        JobOfferOut(
            id=str(o.id),
            sequence=o.sequence,
            transporter_id=str(o.transporter_id),
            transporter_name=name or None,
            transporter_phone=phone,
            status=o.status,
            expires_at=o.expires_at,
            payout_amount=o.payout_amount,
        )
        for o, name, phone in rows
    ]
