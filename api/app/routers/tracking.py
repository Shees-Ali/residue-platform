from fastapi import APIRouter

from app.auth.firebase import AuthUser, as_admin_or_factory
from app.auth.owners import factory_of
from app.deps import DbSession
from app.models.tracking import ActiveTrack
from app.services.tracking import active_tracks

router = APIRouter(prefix="/api/tracking", tags=["tracking"])


@router.get("/active", response_model=list[ActiveTrack])
async def get_active_tracks(db: DbSession, user: AuthUser = as_admin_or_factory):
    """Every load on the move with its last position. A factory sees only its own."""
    factory_id = (await factory_of(db, user)).id if user.role == "factory" else None
    return await active_tracks(db, factory_id)
