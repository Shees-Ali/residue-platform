"""Guarded job state changes. SQL decides who wins a race, not Python."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Job, LedgerEntry
from app.services.job_states import require_transition


async def transition(
    db: AsyncSession, job_id: uuid.UUID, expected: str, new: str, **values
) -> None:
    """Move `expected -> new` only if the job is still in `expected`; else 409.

    The conditional UPDATE makes concurrent callers safe: the loser matches zero rows.
    """
    require_transition(expected, new)
    moved = (
        await db.execute(
            update(Job)
            .where(Job.id == job_id, Job.state == expected)
            .values(state=new, **values)
            .returning(Job.id)
        )
    ).first()
    if moved is None:
        raise HTTPException(409, f"The job is no longer '{expected}'")


async def load_job(db: AsyncSession, job_id: str, *, lock: bool = False) -> Job:
    try:
        key = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Unknown job") from None
    query = select(Job).where(Job.id == key)
    if lock:
        query = query.with_for_update()
    job = (await db.execute(query)).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Unknown job")
    return job


async def add_ledger(
    db: AsyncSession,
    job_id: uuid.UUID | None,
    kind: str,
    amount: int,
    party_uid: str | None = None,
    order_id: uuid.UUID | None = None,
) -> None:
    """Append one ledger row for a job or a product order. Zero amounts are skipped."""
    if amount <= 0:
        return
    db.add(
        LedgerEntry(
            job_id=job_id, order_id=order_id, kind=kind, amount=amount, party_uid=party_uid
        )
    )
    await db.flush()


async def ledger_totals(db: AsyncSession, job_id: uuid.UUID) -> dict[str, int]:
    rows = (
        await db.execute(
            select(LedgerEntry.kind, LedgerEntry.amount).where(LedgerEntry.job_id == job_id)
        )
    ).all()
    totals: dict[str, int] = {}
    for kind, amount in rows:
        totals[kind] = totals.get(kind, 0) + amount
    return totals
