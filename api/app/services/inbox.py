"""Mirror notifications to each person's Firestore inbox, after the Postgres commit (EV3, EV5).

`users/{uid}/inbox/{notification id}`: only that person can read it (deploy/firestore.rules), only
this service writes it. The doc id is the notification id, so delivering twice overwrites the same
doc and never duplicates. A failed write is logged and swallowed: the row keeps `delivered_at`
empty, the request still succeeds, and `sweep` tries again.
"""
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Notification
from app.services.notify import PENDING_KEY

log = logging.getLogger(__name__)

RETENTION = timedelta(days=30)  # Firestore TTL on `expires_at`; Postgres keeps the rows
BATCH = 400  # a Firestore batch holds 500 writes


@dataclass(frozen=True)
class InboxDoc:
    id: str
    uid: str
    type: str
    level: str
    title: str
    body: str
    job_id: str | None
    refresh: list[str]
    created_at: datetime

    def fields(self) -> dict:
        return {
            "type": self.type,
            "level": self.level,
            "title": self.title,
            "body": self.body,
            "job_id": self.job_id,
            "refresh": self.refresh,
            "created_at": self.created_at,
            "expires_at": self.created_at + RETENTION,
        }


class Inbox(Protocol):
    enabled: bool

    async def write(self, docs: list[InboxDoc]) -> list[str]:
        """Write the docs; return the ids that were stored."""
        ...


class NullInbox:
    """No Firestore configured (local dev, tests): nothing is delivered and nothing waits."""

    enabled = False

    async def write(self, docs: list[InboxDoc]) -> list[str]:
        return []


class FakeInbox:
    """Test double. `docs` is what was delivered; set `fail` to simulate an outage."""

    enabled = True

    def __init__(self) -> None:
        self.docs: list[InboxDoc] = []
        self.fail = False
        self.attempts = 0

    async def write(self, docs: list[InboxDoc]) -> list[str]:
        self.attempts += 1
        if self.fail:
            raise ConnectionError("simulated Firestore outage")
        self.docs.extend(docs)
        return [d.id for d in docs]

    def for_uid(self, uid: str) -> list[InboxDoc]:
        return [d for d in self.docs if d.uid == uid]


class FirestoreInbox:
    enabled = True

    def __init__(self) -> None:
        from google.cloud import firestore  # imported lazily: only needed when events are on

        self._client = firestore.AsyncClient()

    async def write(self, docs: list[InboxDoc]) -> list[str]:
        stored: list[str] = []
        for start in range(0, len(docs), BATCH):
            chunk = docs[start : start + BATCH]
            batch = self._client.batch()
            for d in chunk:
                user = self._client.collection("users").document(d.uid)
                ref = user.collection("inbox").document(d.id)
                batch.set(ref, d.fields())
            await batch.commit()
            stored += [d.id for d in chunk]
        return stored


_inbox: Inbox | None = None


def get_inbox() -> Inbox:
    """FastAPI dependency. Firestore only when FIRESTORE_EVENTS=1, else nothing is mirrored."""
    global _inbox
    if _inbox is None:
        _inbox = FirestoreInbox() if os.getenv("FIRESTORE_EVENTS") == "1" else NullInbox()
    return _inbox


async def _send(db: AsyncSession, inbox: Inbox, ids: list) -> int:
    rows = (
        await db.execute(
            select(Notification).where(
                Notification.id.in_(ids),
                Notification.recipient_uid.is_not(None),
                Notification.delivered_at.is_(None),
            )
        )
    ).scalars().all()
    if not rows:
        return 0
    docs = [
        InboxDoc(
            id=str(n.id), uid=n.recipient_uid, type=n.type, level=n.level, title=n.title,
            body=n.body, job_id=str(n.job_id) if n.job_id else None, refresh=list(n.refresh),
            created_at=n.created_at,
        )
        for n in rows
    ]
    stored = await inbox.write(docs)
    if stored:
        await db.execute(
            update(Notification)
            .where(Notification.id.in_([n.id for n in rows if str(n.id) in set(stored)]))
            .values(delivered_at=datetime.now(UTC))
        )
        await db.commit()
    return len(stored)


async def deliver(db: AsyncSession, inbox: Inbox) -> int:
    """Send what this request created. Never raises: Postgres already holds the truth."""
    ids = db.info.pop(PENDING_KEY, [])
    if not ids or not inbox.enabled:
        return 0
    try:
        return await _send(db, inbox, ids)
    except Exception:  # noqa: BLE001 - a missed mirror is retried by the sweeper
        log.warning("inbox delivery failed for %d notifications", len(ids), exc_info=True)
        await db.rollback()
        return 0


async def commit_and_deliver(db: AsyncSession, inbox: Inbox) -> int:
    await db.commit()
    return await deliver(db, inbox)


async def sweep(db: AsyncSession, inbox: Inbox, limit: int = 200) -> int:
    """Retry notifications whose mirror failed. Returns how many were delivered."""
    if not inbox.enabled:
        return 0
    ids = (
        await db.execute(
            select(Notification.id)
            .where(Notification.delivered_at.is_(None), Notification.recipient_uid.is_not(None))
            .order_by(Notification.created_at)
            .limit(limit)
        )
    ).scalars().all()
    if not ids:
        return 0
    try:
        return await _send(db, inbox, list(ids))
    except Exception:  # noqa: BLE001
        log.warning("inbox sweep failed", exc_info=True)
        await db.rollback()
        return 0


async def undelivered_count(db: AsyncSession, inbox: Inbox) -> int:
    """How many notifications are waiting to reach Firestore (0 when it is not in use)."""
    if not inbox.enabled:
        return 0
    return (
        await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.delivered_at.is_(None), Notification.recipient_uid.is_not(None)
            )
        )
    ).scalar_one()
