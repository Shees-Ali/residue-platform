"""A1: rank factories for a lot, create its job, and let an admin override (logged)."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory as FactoryRow
from app.db_models.tables import FactoryCandidate, FactoryResidue, Job, Lot
from app.models.factory import Factory, LotRequest
from app.services.assignment import haversine_km, rank_factories, score_factory
from app.services.economics import get_shares


async def load_factories(db: AsyncSession) -> list[Factory]:
    residues: dict[uuid.UUID, list[str]] = {}
    for fid, code in (
        await db.execute(select(FactoryResidue.factory_id, FactoryResidue.residue_code))
    ).all():
        residues.setdefault(fid, []).append(code)
    rows = (await db.execute(select(FactoryRow))).scalars().all()
    return [
        Factory(
            id=str(f.id),
            accepted_residues=residues.get(f.id, []),
            lat=f.lat,
            lon=f.lon,
            price_per_tonne_cents=f.price_per_tonne,
        )
        for f in rows
    ]


async def assign_lot(db: AsyncSession, lot_id: uuid.UUID) -> Job | None:
    """Rank factories, store the ranking, create the job. None when no factory accepts the lot.

    Idempotent: a lot that already has a job returns it. The caller commits.
    """
    existing = (await db.execute(select(Job).where(Job.lot_id == lot_id))).scalar_one_or_none()
    if existing is not None:
        return existing
    lot = await db.get(Lot, lot_id)
    request = LotRequest(
        residue_type=lot.residue_code,
        lat=lot.lat,
        lon=lot.lon,
        quantity_tonnes=float(lot.quantity_tonnes),
    )
    ranked = rank_factories(await load_factories(db), request)
    if not ranked:
        return None  # the lot stays `open` until a factory that accepts it exists
    for rank, f in enumerate(ranked, start=1):
        db.add(
            FactoryCandidate(
                lot_id=lot.id,
                factory_id=uuid.UUID(f.id),
                rank=rank,
                score=score_factory(f, request),
                distance_km=haversine_km(lot.lat, lot.lon, f.lat, f.lon),
                price_per_tonne=f.price_per_tonne_cents,
                chosen=rank == 1,
            )
        )
    best = ranked[0]
    job = Job(
        lot_id=lot.id,
        factory_id=uuid.UUID(best.id),
        state="created",
        quoted_price_per_tonne=best.price_per_tonne_cents,
        farmer_share_bps=get_shares().farmer_bps,
        est_weight_kg=round(float(lot.quantity_tonnes) * 1000),
    )
    lot.status = "assigned"
    db.add(job)
    await db.flush()
    return job


async def override_factory(
    db: AsyncSession, lot_id: uuid.UUID, factory_id: uuid.UUID, admin_uid: str, reason: str
) -> Job:
    """Admin picks a different eligible factory. Only before escrow is funded. Logged on the row."""
    if not reason.strip():
        raise HTTPException(422, "A reason is required to override the assignment")
    job = (
        await db.execute(select(Job).where(Job.lot_id == lot_id).with_for_update())
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "This lot has no job yet")
    if job.state != "created":
        raise HTTPException(409, "The factory can only be changed before escrow is funded")
    candidates = (
        await db.execute(select(FactoryCandidate).where(FactoryCandidate.lot_id == lot_id))
    ).scalars().all()
    chosen = next((c for c in candidates if c.factory_id == factory_id), None)
    if chosen is None:
        raise HTTPException(422, "That factory is not an eligible candidate for this lot")
    for c in candidates:
        c.chosen = c is chosen
    chosen.overridden_by_uid = admin_uid
    chosen.override_reason = reason.strip()
    job.factory_id = factory_id
    job.quoted_price_per_tonne = chosen.price_per_tonne
    await db.flush()
    return job
