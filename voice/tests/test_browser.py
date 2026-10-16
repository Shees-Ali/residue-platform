import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import browser_routes
from app.main import app

ORIGIN = "http://localhost:5173"
PHONE = "+923001234567"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("BROWSER_CALLS_ENABLED", "true")
    monkeypatch.setenv("BROWSER_ALLOWED_ORIGINS", f"{ORIGIN}, https://demo.web.app")


@pytest.fixture
def fake_call(monkeypatch):
    """Replace the live session: echo mic audio back, barge in once, end when the queue closes."""
    seen = {}

    async def run_call(external_call_id, phone, queue, send_audio, interrupt, **_):
        seen.update(call_id=external_call_id, phone=phone)
        request = await queue.get()  # the first mic frame
        seen["mime"] = request.blob.mime_type
        await interrupt()
        await send_audio(request.blob.data[::-1])
        while not (await queue.get()).close:
            pass
        await send_audio(b"\x00\x00")  # ADK draining after hang-up must not fail the call
        seen["closed"] = True

    monkeypatch.setattr(browser_routes, "run_call", run_call)
    return seen


def _connect(client, origin=ORIGIN):
    headers = {"origin": origin} if origin else {}
    return client.websocket_connect("/browser", headers=headers)


def _refused(origin=ORIGIN):
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), _connect(client, origin) as ws:
        ws.receive_json()


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("BROWSER_CALLS_ENABLED", raising=False)
    _refused()


def test_unknown_or_missing_origin_is_refused(enabled):
    _refused("https://evil.example")
    _refused(None)


@pytest.mark.parametrize(
    "hello", [b"\x01\x02", '{"phone": 923001234567}', '{"phone": null}', "not json", '"x"']
)
def test_malformed_hello_gets_an_error_then_close(enabled, fake_call, hello):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _connect(client) as ws:
        ws.send_bytes(hello) if isinstance(hello, bytes) else ws.send_text(hello)
        assert ws.receive_json()["type"] == "error"
    assert "phone" not in fake_call


def test_call_pumps_audio_both_ways_and_closes_on_hangup(enabled, fake_call):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _connect(client) as ws:
        ws.send_json({"phone": PHONE})
        ws.send_bytes(b"\x01\x02\x03\x04")
        assert ws.receive_json() == {"type": "interrupt"}
        assert ws.receive_bytes() == b"\x04\x03\x02\x01"
    assert fake_call["phone"] == PHONE
    assert fake_call["call_id"].startswith("web-")
    assert fake_call["mime"] == "audio/pcm;rate=16000"
    # the queue closing on hang-up is checked with a stub socket below: TestClient cancels the
    # server task as soon as the client closes, so it cannot observe post-disconnect work


def test_refused_call_sends_an_error(enabled, monkeypatch):
    async def run_call(*_, **__):
        raise RuntimeError("API refused the call: http_422")

    monkeypatch.setattr(browser_routes, "run_call", run_call)
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _connect(client) as ws:
        ws.send_json({"phone": PHONE})
        assert ws.receive_json() == {
            "type": "error",
            "message": "The call ended because of an error.",
        }


def test_agent_ending_first_closes_the_socket(enabled, monkeypatch):
    async def run_call(*_, **__):
        return None  # Gemini ended the session

    monkeypatch.setattr(browser_routes, "run_call", run_call)
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), _connect(client) as ws:
        ws.send_json({"phone": PHONE})
        ws.receive_json()


def test_line_is_busy_when_all_slots_are_taken(enabled, fake_call, monkeypatch):
    monkeypatch.setattr(browser_routes, "_slots", asyncio.Semaphore(0))
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _connect(client) as ws:
        ws.send_json({"phone": PHONE})
        assert "busy" in ws.receive_json()["message"]
    assert "phone" not in fake_call


async def test_sending_after_hangup_does_not_fail_the_call(monkeypatch):
    """Real servers raise on send after disconnect (TestClient does not), so use a stub socket."""
    outcome = {}

    class GoneSocket:
        async def receive(self):
            return {"type": "websocket.disconnect"}

        async def send_bytes(self, _):
            raise RuntimeError("Cannot call send once a close message has been sent")

        send_json = send_bytes

        async def close(self, code=1000):
            outcome["closed"] = code

    async def run_call(_id, _phone, queue, send_audio, interrupt, **_):
        while not (await queue.get()).close:
            pass
        await send_audio(b"\x00\x00")  # ADK still draining
        await interrupt()
        outcome["finished"] = True

    monkeypatch.setattr(browser_routes, "run_call", run_call)
    await browser_routes._call(GoneSocket(), PHONE)
    assert outcome == {"finished": True, "closed": 1000}


def test_time_limit_ends_even_a_stalled_call_and_frees_the_slot(enabled, monkeypatch):
    from app import session

    async def stalled(*_, **__):
        await asyncio.Event().wait()  # ignores the closed queue

    monkeypatch.setattr(browser_routes, "run_call", stalled)
    monkeypatch.setattr(browser_routes, "MAX_CALL_SECONDS", 0.05)
    monkeypatch.setattr(session, "TRANSPORT_GRACE", 0.05)
    slots = asyncio.Semaphore(1)
    monkeypatch.setattr(browser_routes, "_slots", slots)
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _connect(client) as ws:
        ws.send_json({"phone": PHONE})
        assert ws.receive_json()["message"] == "Call time limit reached."
    assert not slots.locked()


def test_slow_teardown_after_cancel_does_not_hold_the_socket_or_slot(enabled, monkeypatch):
    """run_call's shielded teardown can be slow (API down); the browser must not wait for it."""
    from app import session

    cleanup_done = asyncio.Event()

    async def slow_teardown(*_, **__):
        try:
            await asyncio.Event().wait()
        finally:
            # like run_call: shielded record-closing that outlives the cancel
            await asyncio.shield(asyncio.sleep(0.5))
            cleanup_done.set()

    monkeypatch.setattr(browser_routes, "run_call", slow_teardown)
    monkeypatch.setattr(browser_routes, "MAX_CALL_SECONDS", 0.05)
    monkeypatch.setattr(session, "TRANSPORT_GRACE", 0.05)
    slots = asyncio.Semaphore(1)
    monkeypatch.setattr(browser_routes, "_slots", slots)
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _connect(client) as ws:
        ws.send_json({"phone": PHONE})
        assert ws.receive_json()["message"] == "Call time limit reached."
    assert not slots.locked()
    assert not cleanup_done.is_set()  # released before the slow teardown finished
