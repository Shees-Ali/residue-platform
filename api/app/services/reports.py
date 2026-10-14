"""A3: the ledger reconciliation check, transporter payouts and the impact counter."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Farmer, Job, LedgerEntry, Lot, Offer, Village
from app.models.ledger import LedgerEntry as LedgerEntryModel
from app.models.reports import ImpactOut, ImpactRecord, LedgerCheckOut, PayoutOut
from app.services.ledger import escrow_balanced

FINAL_JOB_STATES = ("settled", "rejected")


def _entries(subject: str, kinds: dict[str, int]) -> list[LedgerEntryModel]:
    return [LedgerEntryModel(job_id=subject, kind=k, amount=a) for k, a in kinds.items()]


async def ledger_check(db: AsyncSession) -> LedgerCheckOut:
    """Escrow in must equal everything released, fees and refunds, for every finished job and
    every order. Jobs still in flight are reported as money held, not as errors."""
    rows = (
        await db.execute(
            select(
                LedgerEntry.job_id,
                LedgerEntry.order_id,
                LedgerEntry.kind,
                func.sum(LedgerEntry.amount),
            ).group_by(LedgerEntry.job_id, LedgerEntry.order_id, LedgerEntry.kind)
        )
    ).all()
    by_job: dict[uuid.UUID, dict[str, int]] = {}
    by_order: dict[uuid.UUID, dict[str, int]] = {}
    totals: dict[str, int] = {}
    for job_id, order_id, kind, amount in rows:
        amount = int(amount)
        totals[kind] = totals.get(kind, 0) + amount
        target = by_job.setdefault(job_id, {}) if job_id else by_order.setdefault(order_id, {})
        target[kind] = target.get(kind, 0) + amount

    states: dict[uuid.UUID, str] = {}
    if by_job:
        states = dict(
            (await db.execute(select(Job.id, Job.state).where(Job.id.in_(list(by_job))))).all()
        )
    unbalanced_jobs, held, checked = [], 0, 0
    for job_id, kinds in by_job.items():
        if states.get(job_id) in FINAL_JOB_STATES:
            checked += 1
            if not escrow_balanced(_entries(str(job_id), kinds)):
                unbalanced_jobs.append(str(job_id))
        else:
            held += kinds.get("escrow_in", 0) - sum(
                a for k, a in kinds.items() if k != "escrow_in"
            )
    unbalanced_orders = [
        str(o) for o, kinds in by_order.items() if not escrow_balanced(_entries(str(o), kinds))
    ]
    return LedgerCheckOut(
        balanced=not unbalanced_jobs and not unbalanced_orders,
        jobs_checked=checked,
        orders_checked=len(by_order),
        unbalanced_jobs=unbalanced_jobs,
        unbalanced_orders=unbalanced_orders,
        held_in_escrow=held,
        totals=totals,
    )


async def transporter_payouts(db: AsyncSession, transporter_id: uuid.UUID) -> list[PayoutOut]:
    """Pending (the accepted offer's estimate) until the factory confirms, then released."""
    jobs = (
        await db.execute(
            select(Job).where(Job.transporter_id == transporter_id).order_by(Job.created_at.desc())
        )
    ).scalars().all()
    out = []
    for job in jobs:
        released = (
            await db.execute(
                select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                    LedgerEntry.job_id == job.id, LedgerEntry.kind == "release_transporter"
                )
            )
        ).scalar()
        if released:
            out.append(
                PayoutOut(
                    job_id=str(job.id), state=job.state, status="released", amount=int(released)
                )
            )
            continue
        estimate = (
            await db.execute(
                select(Offer.payout_amount).where(
                    Offer.job_id == job.id,
                    Offer.transporter_id == transporter_id,
                    Offer.status == "accepted",
                )
            )
        ).scalar() or 0
        out.append(
            PayoutOut(job_id=str(job.id), state=job.state, status="pending", amount=int(estimate))
        )
    return out


async def impact(db: AsyncSession, limit: int = 50) -> ImpactOut:
    """Tonnes kept out of burning (settled jobs) and a per-lot traceability record."""
    total_kg, count = (
        await db.execute(
            select(func.coalesce(func.sum(Job.final_weight_kg), 0), func.count()).where(
                Job.state == "settled"
            )
        )
    ).one()
    rows = (
        await db.execute(
            select(Job, Lot, Farmer, Village.name, Village.district)
            .join(Lot, Lot.id == Job.lot_id)
            .join(Farmer, Farmer.id == Lot.farmer_id)
            .outerjoin(Village, Village.id == Lot.village_id)
            .where(Job.state == "settled")
            .order_by(Job.settled_at.desc())
            .limit(limit)
        )
    ).all()
    return ImpactOut(
        tonnes_diverted=int(total_kg) / 1000,
        jobs_settled=int(count),
        records=[
            ImpactRecord(
                job_id=str(j.id),
                lot_id=str(lot.id),
                farmer_id=str(f.id),
                farmer_name=f.name or "Unnamed farmer",
                village=village,
                district=district,
                weight_kg=j.final_weight_kg,
                settled_at=j.settled_at,
            )
            for j, lot, f, village, district in rows
        ],
    )
