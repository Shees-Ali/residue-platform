"""HTTPS client for the API. The only way this service touches data."""
import asyncio
import hashlib
import json

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import get_settings

# Tests set this to an httpx.MockTransport; production leaves it None.
_transport: httpx.AsyncBaseTransport | None = None


async def id_token_headers() -> dict[str, str]:
    """Google ID token (audience = API URL) for the voice service account."""
    settings = get_settings()
    if settings.api_auth_disabled:  # local dev only; the API ignores this flag on Cloud Run
        return {}
    token = await asyncio.to_thread(
        id_token.fetch_id_token, google_requests.Request(), settings.api_base_url
    )
    return {"Authorization": f"Bearer {token}"}


def idempotency_key(call_id: str, tool: str, payload: dict) -> str:
    """Stable per (call, tool, payload) so retries by the model do not duplicate writes."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return f"{call_id}:{tool}:{digest}"


async def post(path: str, call_id: str, tool: str, payload: dict, *, write: bool = True) -> dict:
    """POST to the API and return a dict the agent can act on.

    A 422 is a fixable input problem: its {error, message, valid} body goes back to the model so it
    can ask the farmer again. Any other failure becomes a generic error (no internals leaked).
    """
    headers = await id_token_headers()
    if write:
        headers["Idempotency-Key"] = idempotency_key(call_id, tool, payload)
    url = get_settings().api_base_url.rstrip("/") + path
    try:
        async with httpx.AsyncClient(transport=_transport, timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError:
        return {"error": "service_unavailable", "message": "The service is not reachable."}
    if response.status_code == 422:
        return response.json()
    if response.is_success:
        return response.json()
    return {
        "error": f"http_{response.status_code}",
        "message": "The request could not be completed.",
    }


async def start_call(twilio_call_sid: str, caller_phone: str, kind: str = "intake") -> dict:
    """Transport layer only (not a model tool): link the caller to a farmer, get the call id."""
    return await post(
        "/api/internal/calls",
        twilio_call_sid,
        "start_call",
        {"twilio_call_sid": twilio_call_sid, "caller_phone": caller_phone, "kind": kind},
        write=False,
    )


async def end_call(
    call_id: str, status: str = "completed", transcript: str = "", summary: str = ""
) -> dict:
    """Transport layer only (not a model tool): close the call record."""
    return await post(
        f"/api/internal/calls/{call_id}/end",
        call_id,
        "end_call",
        {"status": status, "transcript": transcript, "summary": summary},
        write=False,
    )
