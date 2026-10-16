"""Reading the bell: keyset paging, unread counts, mark read."""
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Notification
from app.models.notifications import NotificationOut, NotificationPage
from app.validation import FieldErrors

BAD_CURSOR = "That page marker is not valid"


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    """Opaque marker: microseconds since the epoch, a dot, the id."""
    return f"{int(created_at.timestamp() * 1_000_000)}.{row_id.hex}"


def decode_cursor(raw: str) -> tuple[datetime, uuid.UUID]:
    try:
        micros, hex_id = raw.split(".")
        return datetime.fromtimestamp(int(micros) / 1_000_000, UTC), uuid.UUID(hex_id)
    except (ValueError, OverflowError, OSError):
        raise FieldErrors([("before", BAD_CURSOR)], code="invalid_cursor") from None


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=str(n.id), type=n.type, level=n.level, title=n.title, body=n.body,
        job_id=str(n.job_id) if n.job_id else None, refresh=list(n.refresh),
        created_at=n.created_at, read=n.read_at is not None,
    )


async def unread_count(db: AsyncSession, uid: str) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.recipient_uid == uid, Notification.read_at.is_(None)
            )
        )
    ).scalar_one()


async def list_notifications(
    db: AsyncSession, uid: str, *, limit: int, before: str | None, unread_only: bool
) -> NotificationPage:
    query = select(Notification).where(Notification.recipient_uid == uid)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    if before:
        at, row_id = decode_cursor(before)
        query = query.where(
            or_(
                Notification.created_at < at,
                and_(Notification.created_at == at, Notification.id < row_id),
            )
        )
    rows = (
        await db.execute(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
        )
    ).scalars().all()
    more = len(rows) > limit
    page = rows[:limit]
    return NotificationPage(
        items=[_out(n) for n in page],
        next=encode_cursor(page[-1].created_at, page[-1].id) if more else None,
        unread=await unread_count(db, uid),
    )


async def mark_read(db: AsyncSession, uid: str, notification_id: str) -> None:
    """Mark one of the caller's notifications read. Anyone else's id is simply not found."""
    try:
        key = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(404, "Notification not found") from None
    row = (
        await db.execute(
            select(Notification).where(Notification.id == key, Notification.recipient_uid == uid)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await db.flush()


async def mark_all_read(db: AsyncSession, uid: str) -> int:
    done = await db.execute(
        update(Notification)
        .where(Notification.recipient_uid == uid, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    return done.rowcount or 0
