from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_admin
from app.db_models.tables import User
from app.deps import DbSession, Events
from app.models.me import ApproveIn, UserOut
from app.services.registration import change_status, user_out

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    db: DbSession,
    status: Literal["active", "pending", "suspended"] | None = None,
    role: Literal["admin", "transporter", "factory", "buyer", "farmer"] | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: AuthUser = as_admin,
):
    """Accounts, newest first. `?status=pending` is the approval queue."""
    query = select(User)
    if status:
        query = query.where(User.status == status)
    if role:
        query = query.where(User.role == role)
    rows = (
        await db.execute(query.order_by(User.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return [await user_out(db, u) for u in rows]


async def _act(db, events, admin: AuthUser, uid: str, action: str, tier: int = 1) -> UserOut:
    target = await change_status(db, admin.uid, uid, action, tier)
    out = await user_out(db, target)
    await db.commit()
    await events.publish("job.updated")  # dispatch and assignment eligibility may have changed
    return out


@router.post("/{uid}/approve", response_model=UserOut)
async def approve_user(
    db: DbSession,
    events: Events,
    uid: Annotated[str, Path(min_length=1, max_length=128)],
    body: ApproveIn | None = None,
    user: AuthUser = as_admin,
):
    """Approve a pending transporter or factory. `tier` sets a transporter's largest job."""
    return await _act(db, events, user, uid, "approve", (body or ApproveIn()).tier)


@router.post("/{uid}/reject", response_model=UserOut)
async def reject_user(db: DbSession, events: Events, uid: str, user: AuthUser = as_admin):
    return await _act(db, events, user, uid, "reject")


@router.post("/{uid}/suspend", response_model=UserOut)
async def suspend_user(db: DbSession, events: Events, uid: str, user: AuthUser = as_admin):
    """Block an active account. A transporter also stops receiving offers."""
    return await _act(db, events, user, uid, "suspend")


@router.post("/{uid}/reactivate", response_model=UserOut)
async def reactivate_user(db: DbSession, events: Events, uid: str, user: AuthUser = as_admin):
    return await _act(db, events, user, uid, "reactivate")
