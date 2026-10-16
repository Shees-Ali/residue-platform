"""F4 dial-out through the real routes (needs DATABASE_URL, like the other route tests).

The voice service reports the API's call reference back through /api/internal/calls, so the
farmer's answer lands on the call record the button opened.
"""
import json
import uuid

import httpx
import pytest

from app.services import telephony
from tests.helpers import answer, confirm, move_to_delivered, scalar


async def confirmed(api, world):
    await move_to_delivered(api, world)
    await confirm(api, world, weight_kg=2500)


async def press(api, world):
    return await api.post(f"/api/jobs/{world.job_id}/verification-call")


async def voice_start(api, sid, phone, kind="verification"):
    return await api.post(
        "/api/internal/calls", json={"twilio_call_sid": sid, "caller_phone": phone, "kind": kind}
    )


@pytest.fixture
def telnyx(monkeypatch):
    monkeypatch.setenv("TELNYX_API_KEY", "key")
    monkeypatch.setenv("TELNYX_CONNECTION_ID", "conn")
    monkeypatch.setenv("TELNYX_FROM_NUMBER", "+12025550100")
    monkeypatch.setenv("VOICE_STREAM_URL", "wss://voice.example/telnyx/media")
    monkeypatch.setenv("STREAM_SECRET", "s3cret")
    state = {"reply": lambda request: httpx.Response(200, json={"data": {}}), "sent": []}

    def handler(request):
        state["sent"].append(json.loads(request.content))
        return state["reply"](request)

    monkeypatch.setattr(telephony, "_transport", httpx.MockTransport(handler))
    return state


async def test_voice_service_reuses_the_buttons_call_record_and_the_answer_settles(api, world):
    await confirmed(api, world)
    r = await press(api, world)
    assert r.status_code == 200, r.text
    call_id = r.json()["call_id"]
    started = await voice_start(api, f"verify-{call_id}", world.farmer_phone)
    assert started.status_code == 200, started.text
    assert started.json()["call_id"] == call_id  # same record, no second row
    assert (await answer(api, call_id, world, True)).status_code == 200


async def test_a_call_reference_cannot_be_taken_by_another_caller_or_kind(api, world):
    await confirmed(api, world)
    call_id = (await press(api, world)).json()["call_id"]
    sid = f"verify-{call_id}"
    assert (await voice_start(api, sid, "+923001112222")).status_code == 409  # another farmer
    assert (await voice_start(api, sid, world.farmer_phone, kind="intake")).status_code == 409


async def test_dial_places_the_call_and_blocks_an_immediate_redial(api, world, telnyx):
    await confirmed(api, world)
    r = await press(api, world)
    assert r.status_code == 200, r.text
    assert telnyx["sent"][0]["to"] == world.farmer_phone
    assert telnyx["sent"][0]["command_id"] == f"dial-{r.json()['call_id']}"
    assert (await press(api, world)).status_code == 409  # may still be ringing


async def test_refused_dial_marks_the_call_failed_and_allows_a_retry(api, world, telnyx):
    await confirmed(api, world)
    telnyx["reply"] = lambda request: httpx.Response(422)
    assert (await press(api, world)).status_code == 502
    status = await scalar(
        api, "SELECT status FROM calls WHERE kind = 'verification' ORDER BY started_at DESC"
    )
    assert status == "failed"
    telnyx["reply"] = lambda request: httpx.Response(200, json={"data": {}})
    assert (await press(api, world)).status_code == 200


async def test_lost_dial_response_keeps_the_call_record_for_the_stream(api, world, telnyx):
    await confirmed(api, world)

    def lost(request):
        raise httpx.ReadTimeout("response lost")

    telnyx["reply"] = lost
    assert (await press(api, world)).status_code == 504
    call_id = await scalar(
        api, "SELECT id FROM calls WHERE kind = 'verification' AND status = 'in_progress'"
    )
    assert isinstance(call_id, uuid.UUID)  # committed: the ringing call still has its record
    started = await voice_start(api, f"verify-{call_id}", world.farmer_phone)
    assert started.json()["call_id"] == str(call_id)
    assert (await press(api, world)).status_code == 409  # no duplicate call while it may ring


async def test_a_verification_call_connects_only_once(api, world):
    await confirmed(api, world)
    call_id = (await press(api, world)).json()["call_id"]
    sid = f"verify-{call_id}"
    assert (await voice_start(api, sid, world.farmer_phone)).status_code == 200
    replay = await voice_start(api, sid, world.farmer_phone)
    assert replay.status_code == 409  # a replayed stream cannot reuse the farmer's own call
