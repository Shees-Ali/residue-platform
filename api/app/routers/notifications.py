from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.auth.firebase import AuthUser, current_user
from app.deps import DbSession
from app.models.notifications import NotificationPage, ReadAllOut, UnreadOut
from app.services.notification_views import (
    BAD_CURSOR,
    list_notifications,
    mark_all_read,
    mark_read,
    unread_count,
)
from app.validation import FieldErrors

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
async def get_notifications(
    db: DbSession,
    limit: int = 20,
    before: str | None = None,
    unread_only: bool = False,
    user: AuthUser = Depends(current_user),
):
    """My notifications, newest first. Pass `next` back as `before` for older ones."""
    if not 1 <= limit <= 50:
        raise FieldErrors([("limit", "Limit must be between 1 and 50")], code="invalid_limit")
    if before is not None and len(before) > 64:
        raise FieldErrors([("before", BAD_CURSOR)], code="invalid_cursor")
    return await list_notifications(
        db, user.uid, limit=limit, before=before, unread_only=unread_only
    )


@router.get("/unread-count", response_model=UnreadOut)
async def get_unread_count(db: DbSession, user: AuthUser = Depends(current_user)):
    return UnreadOut(unread=await unread_count(db, user.uid))


@router.post("/read-all", response_model=ReadAllOut)
async def post_read_all(db: DbSession, user: AuthUser = Depends(current_user)):
    marked = await mark_all_read(db, user.uid)
    await db.commit()
    return ReadAllOut(marked=marked)


@router.post("/{notification_id}/read", status_code=204)
async def post_read(
    db: DbSession,
    notification_id: Annotated[str, Path(min_length=1, max_length=64)],
    user: AuthUser = Depends(current_user),
):
    await mark_read(db, user.uid, notification_id)
    await db.commit()
