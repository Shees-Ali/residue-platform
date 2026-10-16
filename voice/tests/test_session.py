from types import SimpleNamespace

import pytest
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types

from app import session
from app.call_context import current_call_id, current_transcript


def _event(audio=b"", interrupted=False, heard=None, said=None):
    content = (
        types.Content(parts=[types.Part(inline_data=types.Blob(mime_type="audio/pcm", data=audio))])
        if audio
        else None
    )
    t = lambda text: types.Transcription(text=text, finished=True) if text else None  # noqa: E731
    return SimpleNamespace(
        content=content,
        interrupted=interrupted,
        input_transcription=t(heard),
        output_transcription=t(said),
    )


async def noop(*_):
    pass


@pytest.fixture
def api(monkeypatch):
    calls = {"order": [], "end_replies": []}

    async def start_call(sid, phone, kind):
        calls["start"] = (sid, phone, kind)
        return {"call_id": "call-1", "farmer_known": False}

    async def end_call(call_id, status, transcript=""):
        calls["order"].append("end_call")
        calls["end"] = (call_id, status, transcript)
        return calls["end_replies"].pop(0) if calls["end_replies"] else {}

    monkeypatch.setattr(session.api_client, "start_call", start_call)
    monkeypatch.setattr(session.api_client, "end_call", end_call)
    monkeypatch.setattr(session, "RETRY_DELAY", 0)
    monkeypatch.setattr(session, "AGENT_STOP_GRACE", 0.05)
    return calls


@pytest.fixture
def live(monkeypatch, api):
    """Fake runner: plays `events`, records what ADK would see and the cleanup order."""
    seen = {"events": [], "deleted": []}

    async def run_live(**kwargs):
        seen["kwargs"] = kwargs
        # The call id must be set before ADK starts (tool tasks copy context then).
        seen["call_id"] = current_call_id.get(None)
        try:
            for e in seen["events"]:
                if isinstance(e, Exception):
                    raise e
                yield e
        finally:
            api["order"].append("adk_closed")

    async def delete_session(**kwargs):
        seen["deleted"].append(kwargs["session_id"])

    monkeypatch.setattr(
        session,
        "runner",
        SimpleNamespace(
            run_live=run_live, session_service=SimpleNamespace(delete_session=delete_session)
        ),
    )
    return seen


async def test_run_call_pumps_audio_and_closes_call_record(api, live):
    live["events"] = [
        _event(said="السلام علیکم"),
        _event(audio=b"\x01\x02"),
        _event(interrupted=True),
        _event(heard="گندم کا بھوسا"),
    ]
    audio, interrupts = [], []

    async def send_audio(b):
        audio.append(b)

    async def interrupt():
        interrupts.append(1)

    queue = LiveRequestQueue()
    await session.run_call("CA1", "+923001234567", queue, send_audio, interrupt)

    assert api["start"] == ("CA1", "+923001234567", "intake")
    assert live["call_id"] == "call-1"
    assert live["kwargs"]["session_id"] == "call-1"
    assert audio == [b"\x01\x02"] and interrupts == [1]
    assert api["end"] == ("call-1", "completed", "agent: السلام علیکم\ncaller: گندم کا بھوسا")
    assert queue.closed
    assert live["deleted"] == ["call-1"]  # no ADK session history kept after the call
    assert current_call_id.get(None) is None  # context restored in the same task
    assert current_transcript.get(None) is None


async def test_failed_session_still_closes_call_record_as_failed(api, live):
    live["events"] = [_event(heard="hello"), RuntimeError("live dropped")]
    with pytest.raises(RuntimeError):
        await session.run_call("CA2", "+923001234567", LiveRequestQueue(), noop, noop)
    assert api["end"] == ("call-1", "failed", "caller: hello")
    assert live["deleted"] == ["call-1"]
    assert current_call_id.get(None) is None


async def test_transport_failure_closes_adk_before_the_call_record(api, live):
    live["events"] = [_event(audio=b"\x01"), _event(audio=b"\x02")]

    async def broken_socket(_):
        raise ConnectionError("browser went away")

    with pytest.raises(ConnectionError):
        await session.run_call("CA4", "+923001234567", LiveRequestQueue(), broken_socket, noop)
    assert api["order"] == ["adk_closed", "end_call"]
    assert api["end"][1] == "failed"


async def test_end_call_is_retried_when_the_api_is_briefly_down(api, live):
    api["end_replies"] = [{"error": "service_unavailable"}, {"error": "http_502"}, {}]
    await session.run_call("CA5", "+923001234567", LiveRequestQueue(), noop, noop)
    assert api["order"].count("end_call") == 3


async def test_refused_call_never_starts_the_agent(monkeypatch, live):
    async def start_call(*_):
        return {"error": "http_422", "message": "bad phone"}

    monkeypatch.setattr(session.api_client, "start_call", start_call)
    with pytest.raises(RuntimeError):
        await session.run_call("CA3", "bad", LiveRequestQueue(), noop, noop)
    assert "kwargs" not in live


async def test_opening_is_queued_ahead_of_caller_audio(monkeypatch, live):
    queue = LiveRequestQueue()

    async def start_call(*_):
        queue.send_realtime(types.Blob(data=b"\x00\x00", mime_type="audio/pcm;rate=16000"))
        return {"error": "http_503"}  # refuse, so we can inspect the queue

    monkeypatch.setattr(session.api_client, "start_call", start_call)
    with pytest.raises(RuntimeError):
        await session.run_call("CA6", "+923001234567", queue, noop, noop, opening="Verify job J1")
    first, second = await queue.get(), await queue.get()
    assert first.content.parts[0].text == "Verify job J1"
    assert second.blob is not None


async def test_cancelled_call_still_closes_the_record(api, live):
    import asyncio

    started = asyncio.Event()

    async def hang(_):
        started.set()
        await asyncio.Event().wait()

    live["events"] = [_event(audio=b"\x01")]
    task = asyncio.create_task(
        session.run_call("CA7", "+923001234567", LiveRequestQueue(), hang, noop)
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert api["end"][1] == "failed"
    assert live["deleted"] == ["call-1"]


async def test_raised_end_call_errors_are_retried(api, live, monkeypatch):
    attempts = []

    async def end_call(call_id, status, transcript=""):
        attempts.append(status)
        if len(attempts) < 3:
            raise RuntimeError("ID token fetch failed")
        return {}

    monkeypatch.setattr(session.api_client, "end_call", end_call)
    await session.run_call("CA8", "+923001234567", LiveRequestQueue(), noop, noop)
    assert attempts == ["completed"] * 3


async def test_second_cancel_cannot_cut_adk_teardown_short(api, monkeypatch):
    import asyncio

    order, teardown_started, release, closed = [], asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def run_live(**kwargs):
        try:
            yield _event(audio=b"\x01")
        finally:
            teardown_started.set()
            await release.wait()  # ADK closing its live connection
            order.append("adk_closed")

    async def delete_session(**kwargs):
        order.append("session_deleted")

    async def end_call(call_id, status, transcript=""):
        order.append(f"end_call:{status}")
        closed.set()
        return {}

    monkeypatch.setattr(
        session,
        "runner",
        SimpleNamespace(
            run_live=run_live, session_service=SimpleNamespace(delete_session=delete_session)
        ),
    )
    monkeypatch.setattr(session.api_client, "end_call", end_call)

    in_call = asyncio.Event()

    async def hang(_):
        in_call.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(
        session.run_call("CA9", "+923001234567", LiveRequestQueue(), hang, noop)
    )
    await asyncio.wait_for(in_call.wait(), 1)
    task.cancel()  # lands in send_audio; teardown starts in the shielded task and waits
    await asyncio.wait_for(teardown_started.wait(), 1)
    task.cancel()  # second cancel while ADK is still closing
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(closed.wait(), 1)
    assert order == ["adk_closed", "session_deleted", "end_call:failed"]


async def test_double_cancel_while_waiting_for_the_next_event(api, monkeypatch):
    import asyncio

    order = []
    waiting, teardown_started, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def run_live(**kwargs):
        try:
            waiting.set()
            await asyncio.Event().wait()  # ADK waiting on Gemini for the next event
            yield _event()
        finally:
            teardown_started.set()
            await release.wait()  # nested ADK cleanup that awaits
            order.append("adk_closed")

    async def delete_session(**kwargs):
        order.append("session_deleted")

    monkeypatch.setattr(
        session,
        "runner",
        SimpleNamespace(
            run_live=run_live, session_service=SimpleNamespace(delete_session=delete_session)
        ),
    )
    task = asyncio.create_task(
        session.run_call("CA10", "+923001234567", LiveRequestQueue(), noop, noop)
    )
    await asyncio.wait_for(waiting.wait(), 1)
    task.cancel()
    await asyncio.wait_for(teardown_started.wait(), 1)
    task.cancel()  # must not cut ADK's cleanup short
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    for _ in range(100):
        if "end_call" in api["order"]:
            break
        await asyncio.sleep(0.01)
    assert order == ["adk_closed", "session_deleted"]
    assert api["end"][1] == "failed"


async def test_end_call_rejected_by_the_api_is_not_retried(api, live):
    api["end_replies"] = [{"error": "http_404"}]
    await session.run_call("CA11", "+923001234567", LiveRequestQueue(), noop, noop)
    assert api["order"].count("end_call") == 1
