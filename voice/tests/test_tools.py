"""create_lot against a mocked API (no network, no google-adk needed)."""
import json

import httpx
import pytest

from app import api_client
from app.call_context import current_call_id
from app.tools import create_lot

ARGS = {
    "residue_type": "rice_straw",
    "quantity_tonnes": 2.5,
    "pickup_date": "2026-10-15",
    "pickup_part": "morning",
    "village": "Raiwind",
    "district": "Lahore",
}


@pytest.fixture
def api(monkeypatch):
    """Install a mock API; `seen` records requests, `reply` sets the next response."""
    monkeypatch.setenv("API_AUTH_DISABLED", "true")
    state = {"seen": [], "reply": (201, {"lot_id": "L1", "residue_label": "Rice straw"})}

    def handler(request: httpx.Request) -> httpx.Response:
        state["seen"].append(request)
        status, body = state["reply"]
        return httpx.Response(status, json=body)

    monkeypatch.setattr(api_client, "_transport", httpx.MockTransport(handler))
    token = current_call_id.set("call-123")
    yield state
    current_call_id.reset(token)


async def test_create_lot_posts_the_call_id_from_context_and_no_farmer_identity(api):
    result = await create_lot(**ARGS)
    assert result["lot_id"] == "L1"
    request = api["seen"][0]
    assert request.url.path == "/api/agent/lots"
    body = json.loads(request.content)
    assert body["call_id"] == "call-123"
    assert not [k for k in body if "farmer" in k or "phone" in k]
    assert body["pickup_part"] == "morning"


async def test_retries_reuse_the_idempotency_key_and_changes_get_a_new_one(api):
    await create_lot(**ARGS)
    await create_lot(**ARGS)
    await create_lot(**{**ARGS, "quantity_tonnes": 3})
    keys = [r.headers["Idempotency-Key"] for r in api["seen"]]
    assert keys[0] == keys[1] != keys[2]
    assert keys[0].startswith("call-123:create_lot:")


async def test_a_422_body_goes_back_to_the_model_so_it_can_ask_again(api):
    api["reply"] = (422, {"error": "unknown_district", "message": "Unknown", "valid": ["Lahore"]})
    result = await create_lot(**{**ARGS, "district": "Atlantis"})
    assert result == {"error": "unknown_district", "message": "Unknown", "valid": ["Lahore"]}


async def test_server_errors_become_a_generic_error_without_internals(api):
    api["reply"] = (500, {"detail": "Traceback ... password=hunter2"})
    result = await create_lot(**ARGS)
    assert result["error"] == "http_500"
    assert "hunter2" not in json.dumps(result)


async def test_unreachable_api_is_a_recoverable_error(monkeypatch):
    monkeypatch.setenv("API_AUTH_DISABLED", "true")

    def boom(request):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(api_client, "_transport", httpx.MockTransport(boom))
    token = current_call_id.set("call-123")
    try:
        assert (await create_lot(**ARGS))["error"] == "service_unavailable"
    finally:
        current_call_id.reset(token)


async def test_no_active_call_returns_an_error_instead_of_guessing():
    assert (await create_lot(**ARGS))["error"] == "no_active_call"


async def test_start_and_end_call_use_the_internal_routes(api):
    api["reply"] = (200, {"call_id": "c1", "farmer_known": False})
    assert (await api_client.start_call("CA1", "+923001234567"))["call_id"] == "c1"
    await api_client.end_call("c1", "completed")
    paths = [r.url.path for r in api["seen"]]
    assert paths == ["/api/internal/calls", "/api/internal/calls/c1/end"]
    assert "Idempotency-Key" not in api["seen"][0].headers  # keyed by twilio_call_sid server-side


# --- F2, F3, F4 tools ---------------------------------------------------------------------


async def test_get_quote_posts_the_lot_for_this_call_and_is_not_keyed(api):
    from app.tools import get_quote

    api["reply"] = (200, {"price_per_tonne_rupees": 10_000_000.0, "farmer_share_percent": 70.0})
    result = await get_quote("lot-1")
    assert result["farmer_share_percent"] == 70.0
    request = api["seen"][0]
    assert request.url.path == "/api/agent/quote"
    assert json.loads(request.content) == {"call_id": "call-123", "lot_id": "lot-1"}
    assert "Idempotency-Key" not in request.headers  # a read, not a write


async def test_escalate_sends_a_summary_with_a_stable_key(api):
    from app.tools import escalate_to_human

    api["reply"] = (201, {"escalation_id": "e1", "status": "open"})
    await escalate_to_human("Farmer is upset about the price")
    await escalate_to_human("Farmer is upset about the price")
    first, second = api["seen"]
    assert first.url.path == "/api/agent/escalations"
    assert first.headers["Idempotency-Key"] == second.headers["Idempotency-Key"]
    assert json.loads(first.content)["call_id"] == "call-123"


async def test_record_confirmation_has_no_farmer_identity_and_returns_errors_to_the_model(api):
    from app.tools import record_confirmation

    api["reply"] = (409, {"detail": "The job is 'settled', not waiting for verification"})
    result = await record_confirmation("job-9", True)
    assert result["error"] == "http_409"
    body = json.loads(api["seen"][0].content)
    assert body == {"call_id": "call-123", "job_id": "job-9", "confirmed": True, "note": ""}
    assert not [k for k in body if "farmer" in k or "phone" in k]


async def test_other_tools_refuse_without_an_active_call():
    from app.tools import escalate_to_human, get_quote, record_confirmation

    assert (await get_quote("l"))["error"] == "no_active_call"
    assert (await escalate_to_human("x"))["error"] == "no_active_call"
    assert (await record_confirmation("j", True))["error"] == "no_active_call"
