import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_admin
from app.db_models.tables import Transporter, User
from app.deps import DbSession, Delivery
from app.models.transporter import ApproveIn, TransporterOut
from app.services.dispatch import TIER_MAX_TONNES
from app.services.inbox import commit_and_deliver
from app.services.notify import emit

router = APIRouter(prefix="/api/transporters", tags=["transporters"])


def _out(t: Transporter, name: str | None = None) -> TransporterOut:
    return TransporterOut(
        id=str(t.id),
        user_uid=t.user_uid,
        display_name=name or None,
        phone=t.phone,
        tier=t.tier,
        max_tonnes=float(t.max_tonnes),
        approved=t.approved_at is not None,
        approved_at=t.approved_at,
        lat=t.lat,
        lon=t.lon,
    )


async def _name(db, t: Transporter) -> str | None:
    user = await db.get(User, t.user_uid) if t.user_uid else None
    return user.display_name if user else None


async def _load(db, transporter_id: str) -> Transporter:
    try:
        key = uuid.UUID(transporter_id)
    except ValueError:
        raise HTTPException(404, "Unknown transporter") from None
    transporter = await db.get(Transporter, key)
    if transporter is None:
        raise HTTPException(404, "Unknown transporter")
    return transporter


@router.get("", response_model=list[TransporterOut])
async def get_transporters(db: DbSession, approved: bool | None = None, user: AuthUser = as_admin):
    query = (
        select(Transporter, User.display_name)
        .outerjoin(User, User.uid == Transporter.user_uid)
        .order_by(Transporter.created_at)
    )
    if approved is True:
        query = query.where(Transporter.approved_at.is_not(None))
    elif approved is False:
        query = query.where(Transporter.approved_at.is_(None))
    return [_out(t, name) for t, name in (await db.execute(query)).all()]


@router.post("/{transporter_id}/approve", response_model=TransporterOut)
async def approve_transporter(
    db: DbSession, inbox: Delivery, transporter_id: str, body: ApproveIn, user: AuthUser = as_admin
):
    """Approve (or re-tier) a transporter. The tier sets the largest job they are offered."""
    transporter = await _load(db, transporter_id)
    newly = transporter.approved_at is None
    transporter.tier = body.tier
    transporter.max_tonnes = TIER_MAX_TONNES[body.tier]
    transporter.approved_at = transporter.approved_at or datetime.now(UTC)
    await db.flush()
    out = _out(transporter, await _name(db, transporter))
    if transporter.user_uid:
        await emit(
            db, "account.approved" if newly else "account.tier_changed", actor=user,
            uid=transporter.user_uid, tier=body.tier, max_tonnes=float(transporter.max_tonnes),
        )
    await commit_and_deliver(db, inbox)
    return out


@router.post("/{transporter_id}/revoke", response_model=TransporterOut)
async def revoke_transporter(
    db: DbSession, inbox: Delivery, transporter_id: str, user: AuthUser = as_admin
):
    """Stop offering jobs to this transporter. Jobs they already accepted are unaffected."""
    transporter = await _load(db, transporter_id)
    transporter.approved_at = None
    await db.flush()
    out = _out(transporter, await _name(db, transporter))
    if transporter.user_uid:
        await emit(db, "account.suspended", actor=user, uid=transporter.user_uid)
    await commit_and_deliver(db, inbox)
    return out
