"""Firestore `events` feed: a refetch signal for dashboards, never the source of truth.

Written by the API after the Postgres commit. No money, no personal data. A failed write is
logged and swallowed: Postgres already holds the truth and dashboards can poll as a fallback.
"""
import logging
from datetime import UTC, datetime
from typing import Protocol

log = logging.getLogger(__name__)

EVENT_TYPES = (
    "lot.created",
    "job.updated",
    "offer.created",
    "offer.updated",
    "escalation.created",
    "ledger.updated",
)


class EventSink(Protocol):
    async def publish(self, type: str, job_id: str | None = None) -> None: ...


class NullEvents:
    """Used when Firestore is not configured (local dev without an emulator) and in tests."""

    async def publish(self, type: str, job_id: str | None = None) -> None:
        return None


class FakeEvents:
    """Test double that records what was published."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def publish(self, type: str, job_id: str | None = None) -> None:
        self.sent.append({"type": type, "job_id": job_id})


class FirestoreEvents:
    def __init__(self) -> None:
        from google.cloud import firestore  # imported lazily: only needed when events are on

        self._client = firestore.AsyncClient()

    async def publish(self, type: str, job_id: str | None = None) -> None:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type}")
        doc = {"type": type, "at": datetime.now(UTC)}
        if job_id:
            doc["job_id"] = job_id
        try:
            await self._client.collection("events").add(doc)
        except Exception:  # noqa: BLE001 - never fail the request over a refetch hint
            log.warning("events write failed for %s", type, exc_info=True)


_sink: EventSink | None = None


def get_events() -> EventSink:
    """FastAPI dependency. Firestore only when FIRESTORE_EVENTS=1, else a no-op."""
    global _sink
    if _sink is None:
        import os

        _sink = FirestoreEvents() if os.getenv("FIRESTORE_EVENTS") == "1" else NullEvents()
    return _sink
