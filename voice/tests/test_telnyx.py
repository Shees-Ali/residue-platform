import asyncio
import base64
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import session, telnyx, telnyx_routes
from app.main import app

BASE = "https://voice.example.run.app"
MEDIA = "wss://voice.example.run.app/telnyx/media"
KEY = Ed25519PrivateKey.generate()
INTAKE = {
    "kind": "intake",
    "call_control_id": "v3:abc",
    "external_id": "sess-1",
    "phone": "+923001234567",
}
VERIFY = {
    "kind": "verification",
    "call_ref": "verify-c1",
    "phone": "+923009999999",
    "job_id": "J-7",
    "weight_kg": 8450,
    "farmer_amount_rupees": 38447.5,
}


def _sign(message: bytes, ts: int | None = None, key=KEY) -> dict:
    ts = str(int(time.time()) if ts is None else ts)
    sig = base64.b64encode(key.sign(ts.encode() + b"|" + message)).decode()
    return {"telnyx-signature-ed25519": sig, "telnyx-timestamp": ts}


@pytest.fixture(autouse=True)
def env(monkeypatch):
    public = KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setenv("TELNYX_PUBLIC_KEY", base64.b64encode(public).decode())
    monkeypatch.setenv("TELNYX_API_KEY", "test-key")
    monkeypatch.setenv("PUBLIC_BASE_URL", BASE + "/")
    monkeypatch.setenv("STREAM_SECRET", "s3cret")
    monkeypatch.setattr(telnyx, "RETRY_DELAY", 0)
    monkeypatch.setattr(session, "TRANSPORT_GRACE", 0.05)
    telnyx_routes._seen_streams.clear()
    # Never the real Telnyx API: tests that care about commands use the `rest` fixture instead.
    monkeypatch.setattr(
        telnyx, "_transport", httpx.MockTransport(lambda request: httpx.Response(599))
    )


@pytest.fixture
def rest(monkeypatch):
    """Record Call Control commands instead of calling Telnyx; `replies` overrides the 200s."""
    sent, replies = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.url.path, json.loads(request.content), request.headers))
        return replies.pop(0) if replies else httpx.Response(200, json={"data": {}})

    monkeypatch.setattr(telnyx, "_transport", httpx.MockTransport(handler))
    return {"sent": sent, "replies": replies}


# --- webhook ---------------------------------------------------------------------------------

INCOMING = {
    "data": {
        "event_type": "call.initiated",
        "payload": {
            "call_control_id": "v3:abc",
            "call_session_id": "sess-1",
            "direction": "incoming",
            "from": "+923001234567",
        },
    }
}


def _webhook(client, event: dict, headers: dict | None = None):
    body = json.dumps(event).encode()
    headers = _sign(body) if headers is None else headers
    return client.post("/telnyx/webhook", content=body, headers=headers)


def test_unsigned_stale_tampered_or_foreign_webhooks_are_refused(rest):
    client = TestClient(app)
    body = json.dumps(INCOMING).encode()
    assert _webhook(client, INCOMING, headers={}).status_code == 403
    stale = _sign(body, ts=int(time.time()) - 600)
    assert _webhook(client, INCOMING, headers=stale).status_code == 403
    assert _webhook(client, INCOMING, headers=_sign(body + b" ")).status_code == 403
    foreign = _sign(body, key=Ed25519PrivateKey.generate())
    assert _webhook(client, INCOMING, headers=foreign).status_code == 403
    assert rest["sent"] == []


def test_incoming_call_is_answered_before_the_webhook_returns(rest):
    assert _webhook(TestClient(app), INCOMING).status_code == 200
    path, body, headers = rest["sent"][0]
    assert path == "/v2/calls/v3:abc/actions/answer"
    assert headers["Authorization"] == "Bearer test-key"
    assert body["command_id"] == "answer-v3:abc"  # stable, so Telnyx retries are deduplicated
    assert body["stream_codec"] == body["stream_bidirectional_codec"] == "L16"
    assert body["stream_bidirectional_mode"] == "rtp"
    assert body["stream_bidirectional_target_legs"] == "self"
    base, _, query = body["stream_url"].partition("?")
    assert base == MEDIA
    state = telnyx.stream_state(query)
    assert state.pop("exp") > time.time()
    assert state == INTAKE


def test_failed_answer_is_reported_at_once_so_telnyx_retries(rest):
    rest["replies"].append(httpx.Response(503))
    assert _webhook(TestClient(app), INCOMING).status_code == 502
    assert len(rest["sent"]) == 1  # one quick attempt: Telnyx wants a reply within 2 s


def test_stream_failure_webhooks_hang_up_the_call(rest):
    client = TestClient(app)
    for event in ("streaming.failed", "streaming.stopped"):
        hook = {"data": {"event_type": event, "payload": {"call_control_id": "v3:out"}}}
        assert _webhook(client, hook).status_code == 200
    assert [p for p, _, _ in rest["sent"]] == ["/v2/calls/v3:out/actions/hangup"] * 2
    rest["replies"].append(httpx.Response(422))  # already ended: nothing left to do
    hook = {"data": {"event_type": "streaming.stopped", "payload": {"call_control_id": "v3:x"}}}
    assert _webhook(client, hook).status_code == 200


def test_incoming_call_without_a_session_id_gets_a_short_stable_id(rest):
    event = {"data": {**INCOMING["data"], "payload": {**INCOMING["data"]["payload"]}}}
    del event["data"]["payload"]["call_session_id"]
    assert _webhook(TestClient(app), event).status_code == 200
    state = telnyx.stream_state(rest["sent"][0][1]["stream_url"].partition("?")[2])
    assert state["external_id"].startswith("tx-") and len(state["external_id"]) <= 64


def test_other_or_malformed_events_are_acknowledged_and_ignored(rest):
    client = TestClient(app)
    hangup = {"data": {"event_type": "call.hangup", "payload": {"call_control_id": "v3:abc"}}}
    assert _webhook(client, hangup).status_code == 200
    assert _webhook(client, {"data": "nonsense"}).status_code == 200
    assert rest["sent"] == []


# --- media stream ----------------------------------------------------------------------------


def _start(fmt: dict | None = None, **extra) -> str:
    start = {
        "call_control_id": "v3:abc",
        "call_session_id": "sess-1",
        "from": "+920000000000",  # unsigned: must never be used as identity
        "to": "+920000000001",
        "media_format": fmt or {"encoding": "L16", "sample_rate": 16000, "channels": 1},
        **extra,
    }
    return json.dumps({"event": "start", "start": start})


def _media(pcm_be: bytes) -> str:
    payload = base64.b64encode(pcm_be).decode()
    return json.dumps({"event": "media", "media": {"track": "inbound", "payload": payload}})


def _stream(client, state=INTAKE, query=None):
    query = telnyx.stream_url(state).partition("?")[2] if query is None else query
    return client.websocket_connect("/telnyx/media?" + query)


@pytest.fixture
def fake_call(monkeypatch):
    """Stand-in for run_call: echo one caller frame as agent audio, barge in, wait for close."""
    seen = {}

    async def run_call(external_call_id, phone, queue, send_audio, interrupt, *, kind, opening):
        seen.update(id=external_call_id, phone=phone, kind=kind, opening=opening)
        request = await queue.get()
        seen["caller_audio"] = request.blob.data
        seen["mime"] = request.blob.mime_type
        await send_audio(b"\x00\x10" * 480)  # 20 ms of 24 kHz audio
        await interrupt()
        while not (await queue.get()).close:
            pass
        seen["closed"] = True

    monkeypatch.setattr(telnyx_routes, "run_call", run_call)
    return seen


def _sent_paths(rest, n=1, timeout=5.0):
    """Commands sent so far, waiting briefly: the server may still be finishing after the
    test's socket closes."""
    deadline = time.monotonic() + timeout
    while len(rest["sent"]) < n and time.monotonic() < deadline:
        time.sleep(0.01)
    return [p for p, _, _ in rest["sent"]]


def _refused(client, **kw):
    started = time.monotonic()
    with pytest.raises(WebSocketDisconnect), _stream(client, **kw) as ws:
        ws.receive_text()
    # refused at once, not accepted and later timed out waiting for `start`
    assert time.monotonic() - started < 2


def test_unsigned_tampered_expired_or_unkeyed_streams_are_refused(fake_call, monkeypatch):
    client = TestClient(app)
    good = telnyx.stream_url(INTAKE).partition("?")[2]
    s, t = (part.split("=", 1)[1] for part in good.split("&"))
    _refused(client, query="")
    _refused(client, query=f"s={s}")  # no MAC
    forged = telnyx.stream_url({**INTAKE, "phone": "+923331111111"}).partition("?")[2]
    _refused(client, query=f"{forged.split('&')[0]}&t={t}")  # someone else's state, our MAC
    flipped = t[:-1] + ("A" if t[-1] != "A" else "B")  # always a different MAC
    _refused(client, query=f"s={s}&t={flipped}")  # bad MAC
    expired = telnyx.stream_url(INTAKE, ttl=-1).partition("?")[2]
    _refused(client, query=expired)
    monkeypatch.setenv("STREAM_SECRET", "")
    _refused(client, query=good)  # no secret configured: nothing is valid
    assert fake_call == {}


def test_a_url_signed_with_another_secret_is_refused(fake_call, monkeypatch):
    monkeypatch.setenv("STREAM_SECRET", "other")
    query = telnyx.stream_url(INTAKE).partition("?")[2]
    monkeypatch.setenv("STREAM_SECRET", "s3cret")
    _refused(TestClient(app), query=query)


def test_a_signed_stream_is_accepted_once(fake_call, rest):
    client = TestClient(app)
    with _stream(client) as ws:
        ws.send_text(_start())
        ws.send_text(_media(b"\x00\x01"))
        ws.receive_text()
    _refused(client)  # replay of the same call's stream


def test_unexpected_media_format_hangs_up(fake_call, rest):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(json.dumps({"event": "connected", "version": "1.0.0"}))
        ws.send_text(_start(fmt={"encoding": "PCMU", "sample_rate": 8000, "channels": 1}))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    assert fake_call == {}
    assert _sent_paths(rest)[0] == "/v2/calls/v3:abc/actions/hangup"


def test_forged_start_cannot_pick_the_call_record(fake_call, rest):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(_start(call_session_id="verify-victim-call"))
        ws.send_text(_media(b"\x00\x01"))
        ws.receive_text()
    assert fake_call["id"] == "sess-1"  # from the signed URL


def test_intake_call_streams_both_ways_and_farmer_hangup_needs_no_command(fake_call, rest):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(json.dumps({"event": "connected", "version": "1.0.0"}))
        ws.send_text(_start())
        ws.send_text(_media(b"\x01\x02\x03\x04"))
        out = json.loads(ws.receive_text())
        assert out["event"] == "media"
        assert abs(len(base64.b64decode(out["media"]["payload"])) - 640) <= 4  # 20 ms at 16 kHz
        assert json.loads(ws.receive_text()) == {"event": "clear"}
        ws.send_text(json.dumps({"event": "stop", "stop": {"call_control_id": "v3:abc"}}))
    assert fake_call["caller_audio"] == b"\x01\x02\x03\x04"  # little-endian on both sides
    assert fake_call["mime"] == "audio/pcm;rate=16000"
    # identity comes from the signed URL, not the unsigned start message
    assert (fake_call["id"], fake_call["phone"], fake_call["kind"]) == (
        "sess-1",
        "+923001234567",
        "intake",
    )
    assert fake_call["closed"]
    assert rest["sent"] == []  # Telnyx said the call ended


async def test_broken_stream_still_hangs_up_the_phone_leg(fake_call, rest):
    """Driven with a stub socket: Starlette's TestClient cancels the server task as soon as the
    client closes, so it cannot show what the route does after a disconnect."""
    query = telnyx.stream_url(INTAKE).partition("?")[2]
    incoming = [
        {"type": "websocket.receive", "text": _start()},
        {"type": "websocket.receive", "text": _media(b"\x00\x01")},
        {"type": "websocket.disconnect", "code": 1006},  # the stream broke, no `stop`
    ]

    class BrokenStream:
        scope = {"query_string": query.encode()}

        async def accept(self):
            pass

        async def receive(self):
            if incoming:
                return incoming.pop(0)
            await asyncio.Event().wait()

        async def send_text(self, _):
            pass

        async def close(self, code=1000):
            pass

    await telnyx_routes.media(BrokenStream())
    assert fake_call["closed"]
    assert [p for p, _, _ in rest["sent"]] == ["/v2/calls/v3:abc/actions/hangup"]


def test_agent_ending_the_call_hangs_up_with_retries(monkeypatch, rest):
    async def run_call(*_, **__):
        return None

    monkeypatch.setattr(telnyx_routes, "run_call", run_call)
    rest["replies"].extend([httpx.Response(500), httpx.Response(200)])
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(_start())
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    _sent_paths(rest, n=2)
    hangups = [b for p, b, _ in rest["sent"] if p.endswith("/hangup")]
    assert len(hangups) == 2 and {b["command_id"] for b in hangups} == {"hangup-v3:abc"}


def test_time_limit_hangs_up_a_stalled_call(monkeypatch, rest):
    async def stalled(*_, **__):
        await asyncio.Event().wait()

    monkeypatch.setattr(telnyx_routes, "run_call", stalled)
    monkeypatch.setattr(telnyx_routes, "MAX_CALL_SECONDS", 0.05)
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(_start())
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    assert _sent_paths(rest)[0] == "/v2/calls/v3:abc/actions/hangup"


def test_malformed_stream_messages_are_skipped(fake_call, rest):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(_start())
        ws.send_text("not json")
        ws.send_text(json.dumps({"event": "media", "media": {"payload": "%%%"}}))
        ws.send_text(json.dumps({"event": "media", "media": "x"}))
        ws.send_text(_media(b"\x00\x01"))
        assert json.loads(ws.receive_text())["event"] == "media"
    assert fake_call["caller_audio"] == b"\x00\x01"


def test_verification_call_uses_the_signed_job_and_the_apis_call_record(rest, monkeypatch):
    seen = {}

    async def run_call(external_call_id, phone, queue, send_audio, interrupt, *, kind, opening):
        seen.update(id=external_call_id, phone=phone, kind=kind, opening=opening)
        # the agent ends the call itself, so the hang-up happens while the stream is open

    monkeypatch.setattr(telnyx_routes, "run_call", run_call)
    client = TestClient(app)
    with _stream(client, state=VERIFY) as ws:
        ws.send_text(_start(call_control_id="v3:out"))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    assert seen["kind"] == "verification"
    assert seen["id"] == "verify-c1"  # the call record the API opened
    assert seen["phone"] == "+923009999999"
    assert "J-7" in seen["opening"] and "8450 kg" in seen["opening"]
    assert "38447.5 rupees" in seen["opening"]
    assert rest["sent"][0][0] == "/v2/calls/v3:out/actions/hangup"  # id from start for dials


def test_dialled_call_with_a_bad_format_is_hung_up_by_its_start_id(fake_call, rest):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client, state=VERIFY) as ws:
        bad = {"encoding": "PCMU", "sample_rate": 8000, "channels": 1}
        ws.send_text(_start(fmt=bad, call_control_id="v3:out"))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    assert fake_call == {}
    assert _sent_paths(rest)[0] == "/v2/calls/v3:out/actions/hangup"


def test_no_start_message_closes_without_a_session(fake_call, rest, monkeypatch):
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client, state=VERIFY) as ws:
        ws.close()
    assert fake_call == {}
    assert rest["sent"] == []  # no id yet: Telnyx's streaming.stopped webhook hangs up


def test_agent_audio_goes_out_in_whole_20ms_chunks(monkeypatch, rest):
    async def run_call(_id, _phone, queue, send_audio, interrupt, **_):
        await send_audio(b"\x00\x10" * 240)  # 10 ms at 24 kHz: too short to send alone
        await send_audio(b"\x00\x10" * 480)  # now 30 ms buffered: one 20 ms chunk goes out
        while not (await queue.get()).close:
            pass

    monkeypatch.setattr(telnyx_routes, "run_call", run_call)
    client = TestClient(app)  # held: an unreferenced client can stop its server early
    with _stream(client) as ws:
        ws.send_text(_start())
        sizes = []
        out = json.loads(ws.receive_text())
        sizes.append(len(base64.b64decode(out["media"]["payload"])))
        ws.send_text(json.dumps({"event": "error", "payload": {"code": 1, "title": "x"}}))
        ws.send_text(json.dumps({"event": "stop"}))
    assert sizes and all(n % 640 == 0 for n in sizes)


async def test_quick_commands_have_a_hard_total_deadline(monkeypatch):
    async def slow_send(*_, **__):
        await asyncio.sleep(10)  # a server that trickles bytes forever

    monkeypatch.setattr(telnyx, "WEBHOOK_COMMAND_TIMEOUT", 0.05)
    monkeypatch.setattr(telnyx, "_command", slow_send)
    started = time.monotonic()
    assert await telnyx.answer("v3:abc", INTAKE) is False
    assert time.monotonic() - started < 1


def test_calls_are_not_answered_without_a_stream_secret(rest, monkeypatch):
    monkeypatch.setenv("STREAM_SECRET", "")
    assert _webhook(TestClient(app), INCOMING).status_code == 503
    assert rest["sent"] == []


def test_answered_call_urls_are_short_lived():
    state = telnyx.stream_state(telnyx.stream_url(INTAKE).partition("?")[2])
    assert state["exp"] - time.time() <= telnyx.ANSWER_STREAM_TTL_S + 1


def test_uvicorn_handshake_logs_never_show_stream_tokens(caplog):
    import logging

    import app.main  # noqa: F401  (installs the filter)

    url = telnyx.stream_url(INTAKE).partition(BASE.replace("https://", "wss://"))[2]
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        # the exact call uvicorn's websockets protocol makes when it accepts a connection
        logging.getLogger("uvicorn.error").info(
            '%s - "WebSocket %s" [accepted]', "1.2.3.4:5", url
        )
    assert "/telnyx/media?<redacted>" in caplog.text
    assert "t=" not in caplog.text and "s=" not in caplog.text
