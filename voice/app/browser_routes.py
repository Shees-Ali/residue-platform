"""Browser mic fallback: the same intake_agent over a WebSocket, for demos without a phone line.

Protocol (web/src/pages/Call.tsx is the client):
  client -> {"phone": "+92..."} first (JSON text), then binary frames of 16 kHz 16-bit mono PCM.
  server -> binary frames of 24 kHz 16-bit mono PCM, and {"type": "interrupt"} on barge-in
            (drop any agent audio still queued), {"type": "error", "message": ...} before closing,
            and live events for the page (app.session.Transcript, app.tools):
            {"type": "transcript", "id", "who": "agent"|"caller", "text", "final"},
            {"type": "roman", "id", "roman", "lang", "script"},
            {"type": "lot", ...}, {"type": "quote", ...},
            {"type": "escalated"}, {"type": "confirmation", ...}.
The route is public on purpose (the /phone page stands in for the phone line, which has no
sign-in either): the caller's number is its only identity, like caller ID. So it is off unless
BROWSER_CALLS_ENABLED=true, only accepts origins listed in BROWSER_ALLOWED_ORIGINS, and caps
concurrent calls, call length and calls per client IP (BROWSER_CALLS_PER_IP per 10 minutes).
"""
import asyncio
import contextlib
import json
import logging
import re
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, WebSocket
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types

from app.config import get_settings
from app.session import run_call, stop_agent

router = APIRouter(tags=["browser"])
log = logging.getLogger(__name__)

PHONE = re.compile(r"^\+\d{8,15}$")  # same rule as the API's CallStartIn
MIC_MIME = "audio/pcm;rate=16000"
MAX_CALLS = 2  # per instance: bounds Gemini spend while the route has no auth
MAX_CALL_SECONDS = 600
RATE_WINDOW_S = 600
_slots = asyncio.Semaphore(MAX_CALLS)
_recent: defaultdict[str, deque[float]] = defaultdict(deque)  # client IP -> recent call times


def _client_ip(ws: WebSocket) -> str:
    """The caller's address. Behind Cloud Run or a tunnel the last X-Forwarded-For entry is the
    one the platform's proxy added; the first can be forged by the client."""
    forwarded = ws.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return ws.client.host if ws.client else "unknown"


def _rate_limited(ip: str) -> bool:
    """True when this address already placed its allowance of calls in the window; otherwise
    counts this call. BROWSER_CALLS_PER_IP=0 turns the limit off."""
    limit = get_settings().browser_calls_per_ip
    if limit <= 0:
        return False
    now = time.monotonic()
    calls = _recent[ip]
    while calls and now - calls[0] > RATE_WINDOW_S:
        calls.popleft()
    if len(calls) >= limit:
        return True
    calls.append(now)
    if len(_recent) > 10_000:  # bound memory: drop addresses with nothing in the window
        for key in [k for k, v in _recent.items() if not v or now - v[-1] > RATE_WINDOW_S]:
            del _recent[key]
    return False


async def _hello_phone(ws: WebSocket) -> str | None:
    """The phone number from the first frame, or None if it is missing or malformed."""
    try:
        message = await asyncio.wait_for(ws.receive(), timeout=10)
        hello = json.loads(message.get("text") or "")
    except (TimeoutError, ValueError):
        return None
    phone = hello.get("phone") if isinstance(hello, dict) else None
    return phone if isinstance(phone, str) and PHONE.match(phone) else None


@router.websocket("/browser")
async def browser(ws: WebSocket):
    settings = get_settings()
    if (
        not settings.browser_calls_enabled
        or ws.headers.get("origin") not in settings.browser_allowed_origins
    ):
        await ws.close(code=1008)  # policy violation, before accept: the browser sees 403
        return
    await ws.accept()
    phone = await _hello_phone(ws)
    if phone is None:
        await _fail(ws, "Enter the phone number as +92...")
        return
    if _slots.locked():  # no await between this check and taking the slot
        await _fail(ws, "The line is busy. Try again in a minute.")
        return
    if _rate_limited(_client_ip(ws)):
        await _fail(ws, "Too many calls from this device. Try again in a few minutes.")
        return
    async with _slots:
        await _call(ws, phone)


async def _call(ws: WebSocket, phone: str) -> None:
    queue = LiveRequestQueue()
    hung_up = asyncio.Event()

    async def send(kind: str, data) -> None:
        # After the caller hangs up, ADK still drains buffered audio: drop it quietly so a
        # normal hang-up closes the call record as completed, not failed.
        if hung_up.is_set():
            return
        try:
            await (ws.send_bytes(data) if kind == "bytes" else ws.send_json(data))
        except Exception:  # the socket went away (disconnect, closed transport)
            hung_up.set()

    async def mic() -> None:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                hung_up.set()
                return
            if message.get("bytes"):
                queue.send_realtime(types.Blob(data=message["bytes"], mime_type=MIC_MIME))

    # The typed number is trusted as caller ID (demo line); real phone calls get it from Telnyx.
    agent = asyncio.create_task(
        run_call(
            f"web-{uuid.uuid4().hex}",
            phone,
            queue,
            lambda pcm: send("bytes", pcm),
            lambda: send("json", {"type": "interrupt"}),
            on_event=lambda event: send("json", event),
        )
    )
    listener = asyncio.create_task(mic())
    try:
        done, _ = await asyncio.wait(
            {agent, listener}, timeout=MAX_CALL_SECONDS, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        queue.close()  # first, so even a second cancellation here ends the live session
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)  # only the listener's own cancel
        error = await stop_agent(agent, queue)  # bounded: a stalled agent is cancelled
    if error is not None:
        log.error("browser call failed", exc_info=error)
        await _fail(ws, "The call ended because of an error.")
    elif not done:
        await _fail(ws, "Call time limit reached.")
    else:
        with contextlib.suppress(Exception):
            await ws.close()


async def _fail(ws: WebSocket, message: str) -> None:
    with contextlib.suppress(Exception):
        await ws.send_json({"type": "error", "message": message})
        await ws.close(code=1008)
