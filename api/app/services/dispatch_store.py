"""A2/T1: the offer ladder. One offer at a time, each with an expiry; SQL decides the winner."""
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Job, Lot, Offer, Transporter
from app.models.offer import Offer as OfferModel
from app.services.dispatch import TransporterCandidate, next_transporter, rank_transporters, tick
from app.services.economics import gross, job_shares, offer_ttl_seconds, payouts
from app.services.job_flow import transition
from app.services.notify import emit


@dataclass
class TickResult:
    expired: int = 0
    reoffered: int = 0
    exhausted: int = 0
    dispatched: int = 0
    job_ids: set[str] = field(default_factory=set)


def _now() -> datetime:
    return datetime.now(UTC)


async def _ranked_transporter_ids(db: AsyncSession, lot: Lot) -> list[uuid.UUID]:
    rows = (await db.execute(select(Transporter))).scalars().all()
    candidates = [
        TransporterCandidate(
            str(t.id), t.lat, t.lon, t.max_tonnes, approved=t.approved_at is not None
        )
        for t in rows
    ]
    ranked = rank_transporters(candidates, lot.lat, lot.lon, float(lot.quantity_tonnes))
    return [uuid.UUID(i) for i in ranked]


async def make_next_offer(
    db: AsyncSession, job: Job, now: datetime | None = None
) -> Offer | None:
    """Offer the job to the nearest transporter not yet tried. None when everyone has been asked."""
    now = now or _now()
    lot = await db.get(Lot, job.lot_id)
    tried = (
        await db.execute(select(Offer.transporter_id).where(Offer.job_id == job.id))
    ).scalars().all()
    chosen = next_transporter(
        [str(i) for i in await _ranked_transporter_ids(db, lot)], [str(t) for t in tried]
    )
    if chosen is None:
        return None
    estimate = gross(job.est_weight_kg, job.quoted_price_per_tonne)
    offer = Offer(
        job_id=job.id,
        transporter_id=uuid.UUID(chosen),
        sequence=len(tried) + 1,
        expires_at=now + timedelta(seconds=offer_ttl_seconds()),
        status="pending",
        payout_amount=payouts(estimate, job_shares(job.farmer_share_bps))["transporter"],
    )
    db.add(offer)
    await db.flush()
    await emit(
        db, "offer.created", job_id=job.id, transporter_id=chosen,
        minutes=math.ceil(offer_ttl_seconds() / 60), amount=offer.payout_amount,
    )
    return offer


async def start_dispatch(db: AsyncSession, job: Job, now: datetime | None = None) -> Offer | None:
    """A funded job gets its first offer. No transporter available leaves it `funded`."""
    offer = await make_next_offer(db, job, now)
    if offer is not None:
        await transition(db, job.id, "funded", "offered")
    return offer


async def dispatch_waiting(db: AsyncSession, now: datetime | None = None) -> list[str]:
    """Funded jobs that were never offered (no eligible transporter at the time) get another try.

    Called by the tick, so approving a transporter or raising a tier lets waiting jobs go out.
    """
    waiting = (
        await db.execute(
            select(Job)
            .where(
                Job.state == "funded",
                ~exists().where(Offer.job_id == Job.id),
            )
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    started = []
    for job in waiting:
        if await start_dispatch(db, job, now) is not None:
            started.append(str(job.id))
    return started


async def expire_and_advance(
    db: AsyncSession, now: datetime | None = None, force: bool = False
) -> TickResult:
    """Expire pending offers past their deadline (all of them when `force`) and offer the next.

    `force` is the demo fast-forward. Rows are locked with SKIP LOCKED so two ticks never both
    advance the same offer.
    """
    now = now or _now()
    result = TickResult()
    rows = (
        await db.execute(
            select(Offer).where(Offer.status == "pending").with_for_update(skip_locked=True)
        )
    ).scalars().all()
    models = [
        OfferModel(
            id=str(o.id),
            job_id=str(o.job_id),
            transporter_id=str(o.transporter_id),
            expires_at=o.expires_at,
            status=o.status,
        )
        for o in rows
    ]
    due = {str(i) for i in ([m.id for m in models] if force else tick(models, now))}
    for offer in rows:
        if str(offer.id) not in due:
            continue
        offer.status = "expired"
        result.expired += 1
        await emit(db, "offer.expired", job_id=offer.job_id, transporter_id=offer.transporter_id)
        job = (
            await db.execute(select(Job).where(Job.id == offer.job_id).with_for_update())
        ).scalar_one()
        result.job_ids.add(str(job.id))
        if job.state != "offered":
            continue
        await db.flush()
        nxt = await make_next_offer(db, job, now)
        if nxt is not None:
            result.reoffered += 1
        else:
            await transition(db, job.id, "offered", "funded")
            await emit(db, "job.offers_exhausted", job_id=job.id)
            result.exhausted += 1
    for job_id in await dispatch_waiting(db, now):
        result.dispatched += 1
        result.job_ids.add(job_id)
    await db.flush()
    return result


async def decline_offer(
    db: AsyncSession, offer_id: uuid.UUID, transporter: Transporter, now: datetime | None = None
) -> uuid.UUID:
    """The transporter passes: expire the offer now and send the job to the next transporter.

    Same outcome as the offer lapsing, without waiting for the clock. Returns the job id.
    """
    now = now or _now()
    passed = (
        await db.execute(
            update(Offer)
            .where(
                Offer.id == offer_id,
                Offer.transporter_id == transporter.id,
                Offer.status == "pending",
            )
            .values(status="expired")
            .returning(Offer.job_id)
        )
    ).first()
    if passed is None:
        known = (
            await db.execute(
                select(Offer.id).where(Offer.id == offer_id, Offer.transporter_id == transporter.id)
            )
        ).first()
        if known is None:
            raise HTTPException(404, "Unknown offer")
        raise HTTPException(409, "This offer is no longer open")
    job = (
        await db.execute(select(Job).where(Job.id == passed[0]).with_for_update())
    ).scalar_one()
    await emit(
        db, "offer.declined", job_id=job.id,
        actor=SimpleNamespace(uid=transporter.user_uid, role="transporter"),
    )
    if job.state == "offered" and await make_next_offer(db, job, now) is None:
        await transition(db, job.id, "offered", "funded")  # everyone has been asked
        await emit(db, "job.offers_exhausted", job_id=job.id)
    return job.id


async def accept_offer(
    db: AsyncSession, offer_id: uuid.UUID, transporter: Transporter, now: datetime | None = None
) -> uuid.UUID:
    """Atomic accept: the conditional UPDATE lets exactly one caller win. Returns the job id."""
    now = now or _now()
    won = (
        await db.execute(
            update(Offer)
            .where(
                Offer.id == offer_id,
                Offer.transporter_id == transporter.id,
                Offer.status == "pending",
                Offer.expires_at > now,
            )
            .values(status="accepted")
            .returning(Offer.job_id)
        )
    ).first()
    if won is None:
        exists = (
            await db.execute(
                select(Offer.id).where(Offer.id == offer_id, Offer.transporter_id == transporter.id)
            )
        ).first()
        if exists is None:
            raise HTTPException(404, "Unknown offer")
        raise HTTPException(409, "This offer is no longer available (expired or already taken)")
    job_id = won[0]
    await transition(
        db, job_id, "offered", "accepted", transporter_id=transporter.id, accepted_at=now
    )
    await db.execute(
        update(Offer)
        .where(Offer.job_id == job_id, Offer.status == "pending")
        .values(status="withdrawn")
    )
    await emit(
        db, "job.accepted", job_id=job_id,
        actor=SimpleNamespace(uid=transporter.user_uid, role="transporter"),
    )
    return job_id
