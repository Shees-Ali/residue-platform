"""FA1: the factory funds escrow (simulated), which is what lets dispatch start."""
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, Job
from app.services.dispatch_store import start_dispatch
from app.services.economics import gross
from app.services.job_flow import add_ledger, transition
from app.services.notify import emit


def escrow_amount(job: Job) -> int:
    """What the factory puts in escrow: the estimated weight at the quoted price."""
    return gross(job.est_weight_kg, job.quoted_price_per_tonne)


async def fund_job(
    db: AsyncSession, job: Job, factory: Factory, now: datetime | None = None, actor=None
):
    """created -> funded, write `escrow_in`, then make the first offer. Returns that offer or None.

    No offer exists before this runs, so an unfunded job can never be offered to a transporter.
    """
    now = now or datetime.now(UTC)
    await transition(db, job.id, "created", "funded", funded_at=now)
    await add_ledger(db, job.id, "escrow_in", escrow_amount(job), factory.user_uid)
    await db.refresh(job)
    await emit(db, "job.funded", job_id=job.id, actor=actor, amount=escrow_amount(job))
    return await start_dispatch(db, job, now)
