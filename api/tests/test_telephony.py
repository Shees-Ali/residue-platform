"""F4 dial-out: pure tests (no database), Telnyx replaced by an httpx mock."""
import base64
import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest

from app.db_models.tables import Call, Job
from app.services import telephony
from app.services.economics import gross, job_shares, payouts


def _call_and_job():
    call = Call(id=uuid.uuid4(), kind="verification")
    job = Job(
        id=uuid.uuid4(), quoted_price_per_tonne=650_000, farmer_share_bps=7000, final_weight_kg=8450
    )
    return call, job


@pytest.fixture
def telnyx(monkeypatch):
    monkeypatch.setenv("TELNYX_API_KEY", "key")
    monkeypatch.setenv("TELNYX_CONNECTION_ID", "conn-1")
    monkeypatch.setenv("TELNYX_FROM_NUMBER", "+12025550100")
    monkeypatch.setenv("VOICE_STREAM_URL", "wss://voice.example/telnyx/media")
    monkeypatch.setenv("STREAM_SECRET", "s3cret")
    state = {"reply": httpx.Response(200, json={"data": {"call_session_id": "s"}}), "sent": []}

    def handler(request):
        state["sent"].append(request)
        return state["reply"]

    monkeypatch.setattr(telephony, "_transport", httpx.MockTransport(handler))
    return state


def test_read_back_amount_is_what_settlement_pays():
    call, job = _call_and_job()
    state = telephony.verification_state(call, job, "+923001234567")
    paid = payouts(gross(8450, 650_000), job_shares(7000))["farmer"]  # as settle_verified does
    assert state["farmer_amount_rupees"] == round(paid / 100, 2)
    assert state["weight_kg"] == 8450
    assert state["call_ref"] == f"verify-{call.id}" and len(state["call_ref"]) <= 64
    assert state == {**state, "kind": "verification", "job_id": str(job.id)}


async def test_dial_streams_the_call_to_the_voice_agent_with_the_job(telnyx):
    call, job = _call_and_job()
    await telephony.dial_verification(call, job, "+923001234567")
    request = telnyx["sent"][0]
    body = json.loads(request.content)
    assert request.url == "https://api.telnyx.com/v2/calls"
    assert request.headers["Authorization"] == "Bearer key"
    assert (body["to"], body["from"], body["connection_id"]) == (
        "+923001234567",
        "+12025550100",
        "conn-1",
    )
    base, _, query = body["stream_url"].partition("?")
    assert base == "wss://voice.example/telnyx/media"
    params = dict(p.split("=", 1) for p in query.split("&"))
    encoded, mac = params["s"], params["t"]
    expected = hmac.new(b"s3cret", encoded.encode(), hashlib.sha256).digest()
    assert mac == base64.urlsafe_b64encode(expected).rstrip(b"=").decode()
    assert body["stream_bidirectional_target_legs"] == "self"
    assert body["command_id"] == f"dial-{call.id}"
    assert body["stream_codec"] == body["stream_bidirectional_codec"] == "L16"
    assert body["stream_bidirectional_sampling_rate"] == 16000
    assert "=" not in encoded  # unpadded, as the voice service expects
    state = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    assert state.pop("exp") > time.time()
    assert state == telephony.verification_state(call, job, "+923001234567")
    assert state["phone"] == "+923001234567"


async def test_refused_dial_is_rejected_but_lost_or_failed_responses_are_unknown(
    telnyx, monkeypatch
):
    call, job = _call_and_job()
    telnyx["reply"] = httpx.Response(422, json={"errors": [{"detail": "bad number"}]})
    with pytest.raises(telephony.DialRejected, match="422"):
        await telephony.dial_verification(call, job, "+923001234567")
    telnyx["reply"] = httpx.Response(503)
    with pytest.raises(telephony.DialUnknown):  # Telnyx may still have placed it
        await telephony.dial_verification(call, job, "+923001234567")

    def down(request):
        raise httpx.ReadTimeout("response lost")

    monkeypatch.setattr(telephony, "_transport", httpx.MockTransport(down))
    with pytest.raises(telephony.DialUnknown):
        await telephony.dial_verification(call, job, "+923001234567")


def test_not_configured_means_no_dial(monkeypatch):
    monkeypatch.setenv("STREAM_SECRET", "s3cret")
    monkeypatch.delenv("TELNYX_API_KEY", raising=False)
    assert not telephony.configured()
    monkeypatch.setenv("TELNYX_API_KEY", "key")
    monkeypatch.delenv("STREAM_SECRET")
    assert not telephony.configured()  # unsigned stream URLs would be refused anyway
