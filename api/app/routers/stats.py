from fastapi import APIRouter
from sqlalchemy import func, select

from app.auth.firebase import AuthUser, as_admin
from app.db_models.tables import Escalation, Factory, Farmer, Job, Order, Transporter
from app.deps import DbSession, Delivery
from app.models.stats import StatsOut
from app.services.inbox import undelivered_count
from app.services.reports import ledger_check

router = APIRouter(prefix="/api/stats", tags=["stats"])
FINISHED = ("settled", "rejected", "disputed")


@router.get("", response_model=StatsOut)
async def get_stats(db: DbSession, inbox: Delivery, user: AuthUser = as_admin):
    """The admin overview numbers in one call."""

    async def count(query) -> int:
        return int((await db.execute(query)).scalar() or 0)

    kg = await count(
        select(func.coalesce(func.sum(Job.final_weight_kg), 0)).where(Job.state == "settled")
    )
    return StatsOut(
        farmers=await count(select(func.count()).select_from(Farmer)),
        factories=await count(select(func.count()).select_from(Factory)),
        transporters=await count(
            select(func.count())
            .select_from(Transporter)
            .where(Transporter.approved_at.is_not(None))
        ),
        transporters_waiting_approval=await count(
            select(func.count()).select_from(Transporter).where(Transporter.approved_at.is_(None))
        ),
        live_jobs=await count(
            select(func.count()).select_from(Job).where(Job.state.not_in(FINISHED))
        ),
        jobs_settled=await count(
            select(func.count()).select_from(Job).where(Job.state == "settled")
        ),
        orders=await count(select(func.count()).select_from(Order)),
        tonnes_diverted=kg / 1000,
        escrow_held=(await ledger_check(db)).held_in_escrow,
        notifications_undelivered=await undelivered_count(db, inbox),
        open_escalations=await count(
            select(func.count()).select_from(Escalation).where(Escalation.status == "open")
        ),
    )
