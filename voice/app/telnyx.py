"""Telnyx Call Control: webhook signatures, the signed per-call stream URL, and REST commands.

Webhooks: Telnyx signs `{timestamp}|{body}` with our account's Ed25519 key.
Media streams: Telnyx's own signing of the WebSocket is not something to rely on (its docs
disagree and its reference integration does not use it), so we sign the stream URL ourselves.
The call's details (farmer phone, kind, job, expiry) ride in `s`, and `t` is an HMAC of `s` with
STREAM_SECRET, shared with the API (which signs dialled calls the same way). Telnyx keeps the
query string on the upgrade. Whatever arrives in a valid `s` was put there by us and cannot be
altered or moved to another call; the unsigned `start` message is never trusted for identity.
"""
import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.config import get_settings

API = "https://api.telnyx.com/v2"
SIGNATURE_TOLERANCE_S = 300  # Telnyx's guidance: reject anything older than 5 minutes
STREAM_TTL_S = 300  # longest a stream URL lives (a dialled call can ring a while); replay window
ANSWER_STREAM_TTL_S = 60  # an answered call's stream connects within seconds
RETRY_DELAY = 0.5
WEBHOOK_COMMAND_TIMEOUT = 1.5  # Telnyx expects webhook replies within 2 s
log = logging.getLogger(__name__)

# Tests set this to an httpx.MockTransport; production leaves it None.
_transport: httpx.AsyncBaseTransport | None = None

# Both directions are 16 kHz L16: Gemini's input rate, so the caller's audio needs no resampling.
# Agent audio goes to this call's own leg ("self"): there is no other leg to send it to.
STREAM = {
    "stream_track": "inbound_track",
    "stream_codec": "L16",
    "stream_bidirectional_mode": "rtp",
    "stream_bidirectional_codec": "L16",
    "stream_bidirectional_target_legs": "self",
}


def signed(signature_b64: str | None, timestamp: str | None, message: bytes) -> bool:
    """True if Telnyx signed `{timestamp}|{message}` recently with our account's key."""
    key = get_settings().telnyx_public_key
    if not (key and signature_b64 and timestamp):
        return False
    try:
        if abs(time.time() - int(timestamp)) > SIGNATURE_TOLERANCE_S:
            return False
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key)).verify(
            base64.b64decode(signature_b64), timestamp.encode() + b"|" + message
        )
    except (ValueError, binascii.Error, InvalidSignature):
        return False
    return True


def media_base() -> str:
    return get_settings().public_base_url.replace("https://", "wss://", 1) + "/telnyx/media"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()  # nothing to re-encode in a URL


def _mac(payload: str) -> str:
    key = get_settings().stream_secret.encode()
    return _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())


def stream_url(state: dict, ttl: int = ANSWER_STREAM_TTL_S) -> str:
    """The per-call stream URL: `state` plus an expiry, HMAC-signed with STREAM_SECRET. It works
    as a bearer token (it can show up in request logs), so it is short-lived and single-use.
    The API builds the same URL for dialled calls (api/app/services/telephony.py)."""
    payload = _b64(json.dumps({**state, "exp": int(time.time()) + ttl}).encode())
    return f"{media_base()}?s={payload}&t={_mac(payload)}"


def stream_state(query_string: str) -> dict | None:
    """The state from a stream URL's query string if its HMAC is valid and it has not expired;
    otherwise None. Without a configured STREAM_SECRET nothing is valid."""
    query = parse_qs(query_string)
    payload, mac = (query.get("s") or [""])[0], (query.get("t") or [""])[0]
    if not (get_settings().stream_secret and payload and mac):
        return None
    if not hmac.compare_digest(mac, _mac(payload)):
        return None
    try:
        state = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(state, dict) or not isinstance(state.get("exp"), int):
        return None
    return state if state["exp"] >= time.time() else None


async def command(
    path: str, body: dict, *, attempts: int = 3, timeout: float = 10.0, done_on_ended: bool = False
) -> bool:
    """POST a Call Control command; retried on network errors and 5xx (callers pass a stable
    `command_id`, which Telnyx deduplicates). False if it never succeeded; never raises.
    `timeout` bounds the whole command, not just each network phase.
    `done_on_ended`: 404/422 mean the call already ended, so there is nothing left to do
    (other 4xx, e.g. a bad API key, still fail and are logged)."""
    try:
        async with asyncio.timeout(timeout * attempts + RETRY_DELAY * (2 ** (attempts - 1) - 1)):
            return await _command(path, body, attempts, timeout, done_on_ended)
    except TimeoutError:
        log.error("Telnyx %s timed out", path)
        return False


async def _command(path: str, body: dict, attempts: int, timeout: float, done_on_ended: bool):
    headers = {"Authorization": f"Bearer {get_settings().telnyx_api_key}"}
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(transport=_transport, timeout=timeout) as client:
                response = await client.post(API + path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            outcome = repr(exc)
        else:
            if response.is_success or (done_on_ended and response.status_code in (404, 422)):
                return True
            outcome = f"HTTP {response.status_code}"
            if response.status_code < 500:  # retrying a refused command won't help
                break
        if attempt < attempts - 1:
            await asyncio.sleep(RETRY_DELAY * 2**attempt)
    log.error("Telnyx %s failed: %s", path, outcome)
    return False


async def answer(call_control_id: str, state: dict) -> bool:
    """One quick attempt: Telnyx wants a webhook reply within 2 s and retries it otherwise."""
    return await command(
        f"/calls/{call_control_id}/actions/answer",
        {"stream_url": stream_url(state), "command_id": f"answer-{call_control_id}", **STREAM},
        attempts=1,
        timeout=WEBHOOK_COMMAND_TIMEOUT,
    )


async def hangup(call_control_id: str, *, quick: bool = False) -> bool:
    """Hang up; an already-ended call counts as done. `quick` for use inside a webhook."""
    return await command(
        f"/calls/{call_control_id}/actions/hangup",
        {"command_id": f"hangup-{call_control_id}"},
        done_on_ended=True,
        **({"attempts": 1, "timeout": WEBHOOK_COMMAND_TIMEOUT} if quick else {}),
    )
