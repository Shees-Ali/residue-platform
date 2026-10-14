from fastapi import APIRouter, Depends, HTTPException

from app.auth.firebase import AuthUser
from app.auth.scheduler import scheduler_or_admin
from app.deps import DbSession, Events
from app.models.offer_out import TickIn, TickOut
from app.services.dispatch_store import expire_and_advance

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


@router.post("/tick", response_model=TickOut)
async def tick(
    db: DbSession,
    events: Events,
    body: TickIn | None = None,
    user: AuthUser = Depends(scheduler_or_admin),
):
    """Expire unanswered offers and move each job to its next transporter.

    Called by Cloud Scheduler, or by an admin (the demo fast-forward button with force=true).
    """
    force = bool(body and body.force)
    if force and user.role != "admin":
        raise HTTPException(403, "Only an admin may force-expire offers")
    result = await expire_and_advance(db, force=force)
    await db.commit()
    for job_id in result.job_ids:
        await events.publish("offer.updated", job_id)
        await events.publish("job.updated", job_id)
    return TickOut(
        expired=result.expired,
        reoffered=result.reoffered,
        exhausted=result.exhausted,
        dispatched=result.dispatched,
    )
