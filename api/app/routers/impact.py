from fastapi import APIRouter, Depends, Query

from app.auth.firebase import AuthUser, current_user
from app.deps import DbSession
from app.models.reports import ImpactOut
from app.services.reports import impact

router = APIRouter(prefix="/api/impact", tags=["impact"])


@router.get("", response_model=ImpactOut)
async def get_impact(
    db: DbSession, limit: int = Query(50, ge=1, le=200), user: AuthUser = Depends(current_user)
):
    """Tonnes kept out of burning, plus a record per settled lot (farmer, place, date, weight)."""
    return await impact(db, limit)
