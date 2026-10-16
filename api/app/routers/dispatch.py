from fastapi import APIRouter, Depends, HTTPException

from app.auth.firebase import AuthUser
from app.auth.scheduler import scheduler_or_admin
from app.deps import DbSession, Delivery
from app.models.offer_out import TickIn, TickOut
from app.services.dispatch_store import expire_and_advance
from app.services.inbox import commit_and_deliver, sweep
from app.services.notify import alert_unbalanced_ledger

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


@router.post("/tick", response_model=TickOut)
async def tick(
    db: DbSession,
    inbox: Delivery,
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
    await alert_unbalanced_ledger(db)
    await commit_and_deliver(db, inbox)
    await sweep(db, inbox)  # retry any notification whose mirror failed earlier
    return TickOut(
        expired=result.expired,
        reoffered=result.reoffered,
        exhausted=result.exhausted,
        dispatched=result.dispatched,
    )
