"""Phone line over Telnyx Call Control.

1. Telnyx POSTs `call.initiated` to /telnyx/webhook (Ed25519-signed). We answer before replying,
   asking Telnyx to stream the call both ways as 16 kHz L16 to a per-call stream URL that carries
   the call's details (see app/telnyx.py). A failed answer is a 502, so Telnyx retries.
2. Telnyx opens that URL. Identity and kind come only from its HMAC-signed, expiring state
   (app/telnyx.py); each call's stream is accepted once per instance. Caller audio arrives as
   `media` events; agent audio goes back as `media`, with `clear` on barge-in.
3. Unless Telnyx tells us the call ended (`stop`), we hang the line up when the agent finishes,
   the time limit hits, or the stream breaks, so no phone leg is left open without an agent.
Outbound verification calls (F4) are dialled by the API with the same stream URL scheme.
"""
import asyncio
import base64
import binascii
import contextlib
import hashlib
import json
import logging
import time

from fastapi import APIRouter, Request, Response, WebSocket
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types

from app import telnyx
from app.audio import ToLine, from_line
from app.config import get_settings
from app.session import run_call, stop_agent

router = APIRouter(prefix="/telnyx", tags=["telnyx"])
log = logging.getLogger(__name__)

LINE_MIME = "audio/pcm;rate=16000"
LINE_BYTES_PER_S = 32000  # 16 kHz, 16-bit
LINE_CHUNK = 640  # 20 ms, Telnyx's minimum outbound chunk
MAX_PLAYOUT_S = 5.0
MAX_CALL_SECONDS = 900  # bounds Gemini spend per phone call
# One stream per call: replay guard within this instance, kept as long as a stream URL is valid.
_seen_streams: dict[str, float] = {}


@router.post("/webhook")
async def webhook(request: Request) -> Response:
    body = await request.body()
    if not telnyx.signed(
        request.headers.get("telnyx-signature-ed25519"),
        request.headers.get("telnyx-timestamp"),
        body,
    ):
        return Response(status_code=403)
    try:
        data = json.loads(body)["data"]
        event, payload = data["event_type"], data["payload"]
        call_control_id = payload["call_control_id"]
        if event == "call.initiated" and payload["direction"] == "incoming":
            if not get_settings().stream_secret:  # its stream would be refused: don't answer
                log.error("STREAM_SECRET is not set; not answering call %s", call_control_id)
                return Response(status_code=503)
            # Everything the stream needs, from this signed webhook (never from `start`).
            state = {
                "kind": "intake",
                "call_control_id": call_control_id,
                "external_id": payload.get("call_session_id") or _short_id(call_control_id),
                "phone": payload["from"],
            }
            ok = await telnyx.answer(call_control_id, state)
        elif event in ("streaming.failed", "streaming.stopped"):
            # No audio path any more (stream refused, failed to start, or ended): make sure the
            # phone leg ends too. Covers dialled calls whose id the stream may never learn.
            ok = await telnyx.hangup(call_control_id, quick=True)
        else:
            ok = True
    except (ValueError, KeyError, TypeError):
        return Response(status_code=200)  # not a call event we act on
    # On failure Telnyx retries the webhook; command_id dedupes the command.
    return Response(status_code=200 if ok else 502)


@router.websocket("/media")
async def media(ws: WebSocket):
    state = telnyx.stream_state(ws.scope.get("query_string", b"").decode()) or {}
    key = state.get("call_control_id") or state.get("call_ref")
    if not key or not _first_stream(key):
        await ws.close(code=1008)
        return
    await ws.accept()
    start, ok = await _start_event(ws)
    # Hang-up needs Telnyx's id: ours (signed) for answered calls; for dialled ones only `start`
    # has it (unsigned: at worst a forger could end a call). If even that is missing, Telnyx's
    # signed `streaming.stopped` webhook triggers the hang-up.
    call_control_id = state.get("call_control_id") or start.get("call_control_id")
    if not ok:
        await _hangup(call_control_id)
        with contextlib.suppress(Exception):
            await ws.close(code=1008)
        return

    queue = LiveRequestQueue()
    to_line = ToLine()
    pending = b""  # agent audio not yet sent: Telnyx takes chunks of at least 20 ms
    plays_until = 0.0  # when the farmer will have heard everything sent so far (monotonic)
    call_over = asyncio.Event()  # Telnyx said the call ended: nothing left to hang up
    stream_gone = asyncio.Event()

    async def send(message: dict) -> None:
        if stream_gone.is_set():
            return
        try:
            await ws.send_text(json.dumps(message))
        except Exception:  # the stream broke; the phone leg may still be up
            stream_gone.set()

    async def send_audio(pcm24k: bytes) -> None:
        nonlocal pending, plays_until
        pending += to_line.convert(pcm24k)
        whole = len(pending) - len(pending) % LINE_CHUNK
        if not whole:
            return
        chunk, pending = pending[:whole], pending[whole:]
        plays_until = max(plays_until, time.monotonic()) + len(chunk) / LINE_BYTES_PER_S
        await send({"event": "media", "media": {"payload": base64.b64encode(chunk).decode()}})

    async def interrupt() -> None:
        nonlocal to_line, pending, plays_until
        to_line, pending, plays_until = ToLine(), b"", 0.0  # nothing stale after barge-in
        await send({"event": "clear"})

    async def caller() -> None:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                stream_gone.set()
                return
            try:
                event = json.loads(message.get("text") or "{}")
                if event.get("event") == "stop":
                    call_over.set()
                    stream_gone.set()
                    return
                if event.get("event") == "error":
                    log.warning("Telnyx stream error: %s", event.get("payload"))
                    continue
                media = event.get("media") or {}
                if event.get("event") == "media" and media.get("track", "inbound") == "inbound":
                    audio = from_line(base64.b64decode(media["payload"], validate=True))
                    queue.send_realtime(types.Blob(data=audio, mime_type=LINE_MIME))
            except (ValueError, KeyError, TypeError, AttributeError, binascii.Error):
                log.warning("skipping a malformed Telnyx stream message")

    kind = "verification" if state.get("kind") == "verification" else "intake"
    agent = asyncio.create_task(
        run_call(
            # verification: the API's reference for the call record it opened (services/telephony)
            state.get("call_ref") or state.get("external_id", ""),
            state.get("phone", ""),
            queue,
            send_audio,
            interrupt,
            kind=kind,
            opening=_opening(state),
        )
    )
    listener = asyncio.create_task(caller())
    try:
        await asyncio.wait(
            {agent, listener}, timeout=MAX_CALL_SECONDS, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        queue.close()  # first, so even a second cancellation here ends the live session
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)  # only the listener's own cancel
        error = await stop_agent(agent, queue)  # bounded: a stalled agent is cancelled
        if error is not None:
            log.error("phone call %s failed", call_control_id, exc_info=error)
        if not call_over.is_set():  # agent finished, time limit, or broken stream
            try:
                if not stream_gone.is_set():  # let the farmer hear the agent's last words
                    await asyncio.sleep(min(max(plays_until - time.monotonic(), 0), MAX_PLAYOUT_S))
            finally:  # even if shutdown cancels the wait
                await _hangup(call_control_id)
        with contextlib.suppress(Exception):
            await ws.close()


def _first_stream(key: str) -> bool:
    now = time.monotonic()
    for old in [k for k, t in _seen_streams.items() if now - t > telnyx.STREAM_TTL_S]:
        del _seen_streams[old]
    if key in _seen_streams:
        return False
    _seen_streams[key] = now
    return True


async def _hangup(call_control_id: str | None) -> None:
    if call_control_id and not await telnyx.hangup(call_control_id):
        log.error("could not hang up call %s; it may still be connected", call_control_id)


async def _start_event(ws: WebSocket) -> tuple[dict, bool]:
    """Skip `connected`; return (the `start` payload, usable). Not usable if it never comes or
    the media format is not what we asked for (16 kHz L16); the payload is kept for hang-up."""
    start: dict = {}
    try:
        async with asyncio.timeout(10):
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    return start, False
                event = json.loads(message.get("text") or "{}")
                if event.get("event") != "start":
                    continue
                start = event.get("start") if isinstance(event.get("start"), dict) else {}
                fmt = start.get("media_format") or {}
                if fmt.get("encoding") != "L16" or fmt.get("sample_rate") != 16000:
                    log.error("unexpected Telnyx media format %s", fmt)
                    return start, False
                return start, True
    except (TimeoutError, ValueError, AttributeError):
        return start, False


def _short_id(call_control_id: str) -> str:
    """A stable external id that fits the API's 64-char column."""
    return "tx-" + hashlib.sha256(call_control_id.encode()).hexdigest()[:40]


def _opening(state: dict) -> str:
    """The text turn that starts the agent: a caller, or the job to verify and what to read."""
    if state.get("kind") == "verification":
        return (
            f"This is an outbound verification call for job_id {state.get('job_id')}. "
            f"The factory confirmed {state.get('weight_kg')} kg; the farmer will receive "
            f"{state.get('farmer_amount_rupees')} rupees. Greet the farmer, say both, and ask "
            "whether they agree."
        )
    return "The caller has connected."
