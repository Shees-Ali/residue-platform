from fastapi import APIRouter, Query

from app.auth.firebase import AuthUser, as_admin
from app.deps import DbSession, Events
from app.models.escalation import EscalationOut
from app.services.escalations import list_escalations, resolve_escalation

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


@router.get("", response_model=list[EscalationOut])
async def get_escalations(
    db: DbSession,
    status: str | None = "open",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: AuthUser = as_admin,
):
    """The admin queue: farmers who asked for a person, and disputes (open ones by default)."""
    return await list_escalations(db, status, limit, offset)


@router.post("/{escalation_id}/resolve", status_code=204)
async def post_escalation_resolve(
    db: DbSession, events: Events, escalation_id: str, user: AuthUser = as_admin
):
    await resolve_escalation(db, escalation_id, user.uid)
    await db.commit()
    await events.publish("escalation.created", escalation_id)  # the queue changed: refetch
