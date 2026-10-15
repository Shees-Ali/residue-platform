"""Local stand-in for Cloud Scheduler: advance expired offers every few seconds.

Off unless DISPATCH_LOOP_SECONDS is set, and never on Cloud Run (K_SERVICE), where the Scheduler
calls POST /api/dispatch/tick instead.
"""
import asyncio
import logging
import os
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dispatch_store import expire_and_advance
from app.services.events import EventSink

log = logging.getLogger(__name__)


def loop_seconds() -> float:
    """Seconds between ticks, or 0 when the loop is off."""
    if os.getenv("K_SERVICE"):
        return 0
    try:
        return max(0.0, float(os.getenv("DISPATCH_LOOP_SECONDS", "0")))
    except ValueError:
        return 0


async def run_once(session: AsyncSession, events: EventSink):
    """One tick: expire lapsed offers, offer the next transporter, publish what changed."""
    result = await expire_and_advance(session)
    await session.commit()
    for job_id in result.job_ids:
        await events.publish("offer.updated", job_id)
        await events.publish("job.updated", job_id)
    return result


async def run_forever(
    new_session: Callable[[], AsyncSession], events: EventSink, seconds: float
) -> None:
    while True:
        try:
            async with new_session() as session:
                await run_once(session, events)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the loop must survive a bad tick
            log.exception("dispatch tick failed")
        await asyncio.sleep(seconds)
