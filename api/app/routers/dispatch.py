from fastapi import APIRouter

from app.routers._stub import todo

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


@router.post("/tick")
async def tick():
    """Called by Cloud Scheduler (and the demo fast-forward button) to expire unanswered offers."""
    # TODO(A2): auth (scheduler OIDC or admin), call services.dispatch.tick, persist, re-offer.
    todo("A2")
