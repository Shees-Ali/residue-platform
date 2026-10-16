from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import func, or_, select

from app.auth.firebase import AuthUser, as_admin
from app.db_models.tables import User
from app.deps import DbSession, Delivery
from app.models.me import ApproveIn, UserOut
from app.models.profile import ProfileEditIn, ProfileOut
from app.services.inbox import commit_and_deliver
from app.services.notify import emit
from app.services.profile import profile_out, update_profile
from app.services.registration import change_status, user_out

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(
    db: DbSession,
    status: Literal["active", "pending", "suspended"] | None = None,
    role: Literal["admin", "transporter", "factory", "buyer", "farmer"] | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
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
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(
            or_(func.lower(User.display_name).like(like), func.lower(User.email).like(like))
        )
    rows = (
        await db.execute(query.order_by(User.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return [await user_out(db, u) for u in rows]


ACTION_EVENT = {
    "approve": "account.approved",
    "reject": "account.rejected",
    "suspend": "account.suspended",
    "reactivate": "account.reactivated",
}


async def _act(db, inbox, admin: AuthUser, uid: str, action: str, tier: int = 1) -> UserOut:
    target = await change_status(db, admin.uid, uid, action, tier)
    out = await user_out(db, target)
    await emit(db, ACTION_EVENT[action], actor=admin, uid=target.uid)
    await commit_and_deliver(db, inbox)
    return out


@router.post("/{uid}/approve", response_model=UserOut)
async def approve_user(
    db: DbSession,
    inbox: Delivery,
    uid: Annotated[str, Path(min_length=1, max_length=128)],
    body: ApproveIn | None = None,
    user: AuthUser = as_admin,
):
    """Approve a pending transporter or factory. `tier` sets a transporter's largest job."""
    return await _act(db, inbox, user, uid, "approve", (body or ApproveIn()).tier)


@router.post("/{uid}/reject", response_model=UserOut)
async def reject_user(db: DbSession, inbox: Delivery, uid: str, user: AuthUser = as_admin):
    return await _act(db, inbox, user, uid, "reject")


@router.post("/{uid}/suspend", response_model=UserOut)
async def suspend_user(db: DbSession, inbox: Delivery, uid: str, user: AuthUser = as_admin):
    """Block an active account. A transporter also stops receiving offers."""
    return await _act(db, inbox, user, uid, "suspend")


@router.post("/{uid}/reactivate", response_model=UserOut)
async def reactivate_user(db: DbSession, inbox: Delivery, uid: str, user: AuthUser = as_admin):
    return await _act(db, inbox, user, uid, "reactivate")


async def _target(db: DbSession, uid: str) -> User:
    target = await db.get(User, uid)
    if target is None:
        raise HTTPException(404, "Unknown user")
    return target


@router.get("/{uid}/profile", response_model=ProfileOut)
async def get_user_profile(
    db: DbSession,
    uid: Annotated[str, Path(min_length=1, max_length=128)],
    user: AuthUser = as_admin,
):
    """Admin: one person's editable details."""
    return await profile_out(db, await _target(db, uid))


@router.patch("/{uid}/profile", response_model=ProfileOut)
async def patch_user_profile(
    db: DbSession,
    inbox: Delivery,
    uid: Annotated[str, Path(min_length=1, max_length=128)],
    body: ProfileEditIn,
    user: AuthUser = as_admin,
):
    """Admin: change anyone's details, a transporter's tier and max load included."""
    target = await _target(db, uid)
    async with db.begin_nested():
        await update_profile(db, target, body, admin=True)
    out = await profile_out(db, target)
    sent = body.transporter
    if sent is not None and sent.tier is not None and out.transporter is not None:
        await emit(
            db, "account.tier_changed", actor=user, uid=target.uid,
            tier=out.transporter.tier, max_tonnes=out.transporter.max_tonnes,
        )
    if body.model_fields_set - {"transporter"}:
        await emit(db, "account.edited", actor=user, uid=target.uid)
    await commit_and_deliver(db, inbox)
    return out
