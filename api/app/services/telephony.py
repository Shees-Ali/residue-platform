"""F4: place the farmer's verification call through Telnyx Call Control.

The API only dials. Telnyx streams the answered call to the voice service (`VOICE_STREAM_URL`);
the stream URL's `s` parameter tells it the farmer, the job and what to read back, and `t` is an
HMAC of `s` with STREAM_SECRET (shared with the voice service), so the voice service trusts it
(see voice/app/telnyx.py, which builds answered calls' URLs the same way). The call row's
`twilio_call_sid` holds a stable reference the voice service reports back through
`/api/internal/calls`, so the agent's tools act on this exact call record.
Not configured (no TELNYX_API_KEY or STREAM_SECRET) = no dial: the demo button only opens
the call record.
"""
import base64
import hashlib
import hmac
import json
import os
import time

import httpx

from app.db_models.tables import Call, Job
from app.services.economics import gross, job_shares, payouts

# Tests set this to an httpx.MockTransport; production leaves it None.
_transport: httpx.AsyncBaseTransport | None = None


class DialError(Exception):
    pass


class DialRejected(DialError):
    """Telnyx answered and refused: no call was placed."""


class DialUnknown(DialError):
    """No answer from Telnyx: the call may or may not be ringing."""


REDIAL_GUARD_S = 180  # a fresh verification call for the same farmer blocks another dial
STREAM_TTL_S = 300  # the stream URL must be used within this; covers ringing (Telnyx timeout 30 s)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def stream_url(state: dict) -> str:
    """Same format as voice/app/telnyx.py stream_url: `s` = state + expiry, `t` = its HMAC."""
    payload = _b64(json.dumps({**state, "exp": int(time.time()) + STREAM_TTL_S}).encode())
    key = os.getenv("STREAM_SECRET", "").encode()
    mac = _b64(hmac.new(key, payload.encode(), hashlib.sha256).digest())
    return f"{os.getenv('VOICE_STREAM_URL', '')}?s={payload}&t={mac}"


def configured() -> bool:
    return bool(os.getenv("TELNYX_API_KEY") and os.getenv("STREAM_SECRET"))


def call_ref(call: Call) -> str:
    """Stable external id for a verification call (fits the 64-char column)."""
    return f"verify-{call.id}"


def verification_state(call: Call, job: Job, farmer_phone: str) -> dict:
    """What the agent reads back: the confirmed weight and the farmer's amount, as settlement
    will pay it (same economics functions, so the call matches the ledger)."""
    farmer = payouts(
        gross(job.final_weight_kg, job.quoted_price_per_tonne), job_shares(job.farmer_share_bps)
    )["farmer"]
    return {
        "kind": "verification",
        "call_ref": call_ref(call),
        "phone": farmer_phone,
        "job_id": str(job.id),
        "weight_kg": job.final_weight_kg,
        "farmer_amount_rupees": round(farmer / 100, 2),
    }


async def dial_verification(call: Call, job: Job, farmer_phone: str) -> None:
    """Ask Telnyx to call the farmer and stream the call to the voice agent.

    Raises DialRejected (nothing placed) or DialUnknown (maybe placed: keep the call record).
    """
    body = {
        "connection_id": os.getenv("TELNYX_CONNECTION_ID", ""),
        "to": farmer_phone,
        "from": os.getenv("TELNYX_FROM_NUMBER", ""),
        "stream_url": stream_url(verification_state(call, job, farmer_phone)),
        "command_id": f"dial-{call.id}",
        "stream_track": "inbound_track",
        "stream_codec": "L16",
        "stream_bidirectional_mode": "rtp",
        "stream_bidirectional_codec": "L16",
        "stream_bidirectional_sampling_rate": 16000,
        # A dialled call has only its own leg; the default ("opposite") would play to nobody.
        "stream_bidirectional_target_legs": "self",
    }
    headers = {"Authorization": f"Bearer {os.getenv('TELNYX_API_KEY', '')}"}
    try:
        async with httpx.AsyncClient(transport=_transport, timeout=10.0) as client:
            response = await client.post(
                "https://api.telnyx.com/v2/calls", json=body, headers=headers
            )
    except httpx.HTTPError as exc:  # sent or not, we cannot tell
        raise DialUnknown("No answer from Telnyx; the farmer's phone may be ringing") from exc
    if response.status_code >= 500:
        raise DialUnknown(f"Telnyx failed (HTTP {response.status_code}); the call may be placed")
    if not response.is_success:
        raise DialRejected(f"Telnyx refused the call (HTTP {response.status_code})")
