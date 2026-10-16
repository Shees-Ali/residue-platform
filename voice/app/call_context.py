"""Per-call state set by the transport layer (Twilio/browser), never by the model.

Tools read the call id from here, so the model cannot choose whose call it is acting for.
"""
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

CallEvents = Callable[[dict], Awaitable[None]]

current_call_id: ContextVar[str] = ContextVar("current_call_id")
# Where to send live events for the caller's screen (transcript, captured lot); browser only.
call_events: ContextVar[CallEvents | None] = ContextVar("call_events", default=None)
# Finished caller/agent lines so far, appended by the transport (app.session).
current_transcript: ContextVar[list[str]] = ContextVar("current_transcript")
# Transcript frozen per escalation summary, so a model retry sends the same body (same key).
escalation_snapshots: ContextVar[dict[str, str]] = ContextVar("escalation_snapshots")


async def emit(event: dict) -> None:
    """Send a live event to the caller's screen, if it has one. Display only: never fails."""
    send = call_events.get()
    if send is None:
        return
    try:
        await send(event)
    except Exception:
        logging.getLogger(__name__).debug("live event not delivered", exc_info=True)
