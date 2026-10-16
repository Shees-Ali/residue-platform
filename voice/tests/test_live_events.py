"""Live call-page events: transcript streaming, Roman Urdu, and tool results."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app import api_client, roman, session
from app.call_context import call_events, current_call_id


@pytest.fixture
def screen():
    """Collect live events the way the browser route would receive them."""
    events = []

    async def send(event):
        events.append(event)

    token = call_events.set(send)
    yield events
    call_events.reset(token)


@pytest.fixture
def no_roman(monkeypatch):
    async def fake(text):
        return {"roman": f"R:{text}", "lang": "ur", "script": f"U:{text}"}

    monkeypatch.setattr(session, "romanize", fake)


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


def _lines(screen):
    return [
        (e["id"], e["order"], e["who"], e["text"], e["final"])
        for e in screen
        if e["type"] == "transcript"
    ]


async def test_agent_pieces_grow_one_turn_and_finished_lines_get_roman_urdu(screen, no_roman):
    lines = session.Transcript()
    await lines.heard("agent", "Assalam ", False)
    await lines.heard("agent", "o alaikum", False)
    await lines.heard("agent", "Assalam o alaikum", True)
    await lines.heard("caller", "گندم کا بھوسا", True)
    await _settle()
    assert _lines(screen) == [
        (1, 1, "agent", "Assalam ", False),
        (1, 1, "agent", "Assalam o alaikum", False),
        (1, 1, "agent", "Assalam o alaikum", True),
        (2, 2, "caller", "گندم کا بھوسا", True),
    ]
    romans = sorted((e["id"], e["roman"]) for e in screen if e["type"] == "roman")
    assert romans == [(1, "R:Assalam o alaikum"), (2, "R:گندم کا بھوسا")]


async def test_a_caller_line_arriving_mid_reply_is_placed_before_that_reply(screen, no_roman):
    lines = session.Transcript()
    await lines.heard("agent", "Ji, ", False)  # turn 1: the agent is already answering
    await lines.heard("caller", "Gandum ka bhoosa", True)  # Gemini 3.x sends this late
    await lines.heard("agent", "Ji, bilkul", True)
    assert _lines(screen) == [
        (1, 1, "agent", "Ji, ", False),
        (2, 0.5, "caller", "Gandum ka bhoosa", True),  # ordered before turn 1
        (1, 1, "agent", "Ji, bilkul", True),
    ]
    await lines.close()


async def test_caller_pieces_are_ignored_until_the_line_is_finished(screen, no_roman):
    lines = session.Transcript()
    await lines.heard("caller", "Gan", False)
    await lines.heard("caller", "Gandum", True)
    assert [(e["id"], e["text"]) for e in screen if e["type"] == "transcript"] == [(1, "Gandum")]
    await lines.close()


async def test_an_open_agent_turn_is_closed_on_turn_end_with_the_longer_text(screen, no_roman):
    lines = session.Transcript()
    await lines.heard("agent", "Aap ki lot ", False)
    await lines.heard("agent", "save ho gayi", False)
    await lines.end_agent_turn()  # interrupted before ADK sent a finished line
    await lines.end_agent_turn()  # nothing open: no duplicate
    await lines.heard("agent", "Ab ", False)
    await lines.heard("agent", "Ab", True)
    finals = [(i, t) for i, _, w, t, f in _lines(screen) if f]
    assert finals == [(1, "Aap ki lot save ho gayi"), (2, "Ab")]
    await lines.heard("agent", "Phir ", False)
    await lines.heard("agent", "milte", False)
    await lines.heard("agent", "milte", True)  # ADK lost "Phir " in a reconnect
    assert _lines(screen)[-1][3] == "Phir milte"
    await lines.close()


async def test_a_new_agent_turn_starts_after_a_finished_one(screen, no_roman):
    lines = session.Transcript()
    await lines.heard("agent", "Ji", True)
    await lines.heard("agent", "Aur", False)
    assert [e["id"] for e in screen if e["type"] == "transcript"] == [1, 2]
    await lines.close()


async def test_close_cancels_pending_conversions_so_nothing_is_sent_after_the_call(
    screen, monkeypatch
):
    started = asyncio.Event()

    async def slow(text):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(session, "romanize", slow)
    lines = session.Transcript()
    await lines.heard("caller", "سلام", True)
    await asyncio.wait_for(started.wait(), 1)
    await lines.close()
    assert not lines._romanizing
    assert [e["type"] for e in screen] == ["transcript"]

    async def fails(text):
        return None

    monkeypatch.setattr(session, "romanize", fails)
    monkeypatch.setattr(session, "ROMAN_RETRY_DELAY", 3600)  # parked in the retry sleep
    lines = session.Transcript()
    await lines.heard("caller", "x", True)
    await _settle()
    await asyncio.wait_for(lines.close(), 1)
    assert not lines._romanizing


async def test_failed_roman_urdu_is_retried_once_then_left_alone(screen, monkeypatch):
    calls = []

    async def flaky(text):
        calls.append(text)
        return None if len(calls) == 1 else {"roman": "Salaam"}

    monkeypatch.setattr(session, "romanize", flaky)
    monkeypatch.setattr(session, "ROMAN_RETRY_DELAY", 0)
    lines = session.Transcript()
    await lines.heard("caller", "سلام", True)
    await _settle()
    assert [e["type"] for e in screen] == ["transcript", "roman"] and len(calls) == 2

    async def down(text):
        calls.append(text)
        return None

    monkeypatch.setattr(session, "romanize", down)
    screen.clear()
    await lines.heard("caller", "x", True)
    await _settle()
    assert [e["type"] for e in screen] == ["transcript"]
    await lines.close()


def _event(**kw):
    base = dict(
        interrupted=False,
        turn_complete=False,
        content=None,
        input_transcription=None,
        output_transcription=None,
    )
    return SimpleNamespace(**{**base, **kw})


async def test_converse_only_streams_lines_when_a_screen_listens(monkeypatch, no_roman):
    events = [
        _event(output_transcription=SimpleNamespace(text="Ji, ", finished=False)),
        _event(turn_complete=True),  # ended without a finished line
    ]

    async def run_live(**_):
        for e in events:
            yield e

    monkeypatch.setattr(session, "runner", SimpleNamespace(run_live=run_live))

    async def noop(*_):
        pass

    await session._converse("c1", None, noop, noop, [])  # no screen: nothing to send
    seen = []

    async def send(event):
        seen.append(event)

    token = call_events.set(send)
    try:
        await session._converse("c1", None, noop, noop, [])
    finally:
        call_events.reset(token)
    finals = [e for e in seen if e["type"] == "transcript" and e["final"]]
    assert [e["text"] for e in finals] == ["Ji,"]  # closed on turn_complete


async def test_run_call_wires_on_event_to_the_screen_and_resets_it(monkeypatch, no_roman):
    from google.adk.agents.live_request_queue import LiveRequestQueue

    from app.call_context import emit

    async def start_call(*_):
        return {"call_id": "call-9"}

    async def end_call(*_, **__):
        return {}

    async def run_live(**_):
        await emit({"type": "lot", "lot_id": "L9"})  # what a tool does mid-call
        yield _event(input_transcription=SimpleNamespace(text="Salaam", finished=True))

    async def delete_session(**_):
        pass

    monkeypatch.setattr(session.api_client, "start_call", start_call)
    monkeypatch.setattr(session.api_client, "end_call", end_call)
    monkeypatch.setattr(
        session,
        "runner",
        SimpleNamespace(
            run_live=run_live, session_service=SimpleNamespace(delete_session=delete_session)
        ),
    )
    seen = []

    async def on_event(event):
        seen.append(event)

    async def noop(*_):
        pass

    queue = LiveRequestQueue()
    await session.run_call("web-1", "+923001234567", queue, noop, noop, on_event=on_event)
    assert seen[0] == {"type": "lot", "lot_id": "L9"}
    assert seen[1]["who"] == "caller" and seen[1]["text"] == "Salaam"
    assert call_events.get() is None  # reset after the call


# --- Roman Urdu -------------------------------------------------------------------------------


class FakeModels:
    def __init__(self, answers):
        self.answers, self.asked = answers, []

    async def generate_content(self, model, contents, config):
        self.asked.append(model)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(text=answer)


def _client(monkeypatch, answers):
    models = FakeModels(answers)
    monkeypatch.setattr(roman, "_client", SimpleNamespace(aio=SimpleNamespace(models=models)))
    monkeypatch.setattr(roman, "MODELS", ["m1", "m2", "m3"])
    return models


async def test_romanize_falls_back_to_the_next_model_on_overload(monkeypatch):
    models = _client(
        monkeypatch,
        [
            RuntimeError("503 UNAVAILABLE"),
            '{"lang": "ur", "roman": " Gandum ka bhoosa ", "script": "گندم"}',
        ],
    )
    assert await roman.romanize("گندم کا بھوسا") == {
        "roman": "Gandum ka bhoosa",
        "lang": "ur",
        "script": "گندم",
    }
    assert models.asked == ["m1", "m2"]


async def test_an_unusable_answer_falls_through_to_the_next_model(monkeypatch):
    models = _client(monkeypatch, ['["list"]', '{"roman": "Salaam"}'])
    assert await roman.romanize("سلام") == {"roman": "Salaam", "lang": "other"}
    assert models.asked == ["m1", "m2"]


async def test_each_supported_language_is_tagged_and_unknown_ones_are_other(monkeypatch):
    answers = [
        '{"lang": "pa", "roman": "Kanak di toori ae", "script": "کنک دی توڑی اے"}',
        '{"lang": "ps", "roman": "Da ghanamo bus dey", "script": "د غنمو بوس دی"}',
        '{"lang": "sd", "roman": "Kanak jo bhoso aahe", "script": "ڪڻڪ جو ڀوسو آهي"}',
        '{"lang": "skr", "roman": "Kanak da bhoosa hai"}',
        '{"lang": "en", "roman": "Hello", "script": ""}',
        '{"lang": "klingon", "roman": "nuqneH"}',
        '{"lang": ["ur", "pa"], "roman": "Mix"}',
        '{"lang": " UR ", "roman": "Ji"}',
    ]
    _client(monkeypatch, answers)
    roman.MODELS = ["m1"]
    tags = [(await roman.romanize("x"))["lang"] for _ in range(8)]
    assert tags == ["pa", "ps", "sd", "skr", "en", "other", "other", "ur"]


async def test_romanize_gives_up_quietly(monkeypatch):
    _client(monkeypatch, [RuntimeError("503")] * 3)
    assert await roman.romanize("x") is None
    _client(monkeypatch, ["not json", '["list"]', '{"urdu": "only"}'])
    assert await roman.romanize("x") is None  # every model gave an unusable answer
    assert await roman.romanize("   ") is None


async def test_romanize_respects_its_time_budget(monkeypatch):
    class Slow:
        async def generate_content(self, **_):
            await asyncio.Event().wait()

    monkeypatch.setattr(roman, "_client", SimpleNamespace(aio=SimpleNamespace(models=Slow())))
    monkeypatch.setattr(roman, "TIMEOUT_S", 0.05)
    assert await roman.romanize("x") is None


# --- tool results on the screen ---------------------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    state = {"reply": (201, {})}

    def handler(request):
        status, body = state["reply"]
        return httpx.Response(status, json=body)

    monkeypatch.setattr(api_client, "_transport", httpx.MockTransport(handler))
    monkeypatch.setenv("API_AUTH_DISABLED", "true")
    token = current_call_id.set("call-1")
    yield state
    current_call_id.reset(token)


async def test_saved_lot_is_shown_but_errors_are_not(api, screen):
    from app.tools import create_lot

    api["reply"] = (201, {"lot_id": "L1", "residue_label": "Wheat straw", "factory": "x"})
    await create_lot("wheat_straw", 2, "2026-10-17", "morning", "Raiwind", "Lahore")
    api["reply"] = (422, {"error": "unknown_district", "message": "?", "valid": []})
    await create_lot("wheat_straw", 2, "2026-10-17", "morning", "Raiwind", "Mars")
    assert screen == [{"type": "lot", "lot_id": "L1", "residue_label": "Wheat straw"}]


async def test_quote_and_escalation_are_shown(api, screen):
    from app.tools import escalate_to_human, get_quote

    api["reply"] = (200, {"price_per_tonne_rupees": 7000, "farmer_share_percent": 70})
    await get_quote("L1")
    api["reply"] = (201, {"escalation_id": "e1", "status": "open"})
    await escalate_to_human("Caller wants a person")
    assert screen == [
        {
            "type": "quote",
            "lot_id": "L1",
            "price_per_tonne_rupees": 7000,
            "farmer_share_percent": 70,
        },
        {"type": "escalated", "escalation_id": "e1"},
    ]


async def test_check_status_sends_only_the_call_id_and_shows_the_requests(api, screen):
    import json

    from app.tools import check_status

    sent = []
    original = api_client._transport

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"requests": [{"lot_id": "L1", "stage": "on_the_way"}]})

    api_client._transport = httpx.MockTransport(handler)
    try:
        result = await check_status()
    finally:
        api_client._transport = original
    assert sent == [{"call_id": "call-1"}]  # identity comes from the call, never the model
    assert result["requests"][0]["stage"] == "on_the_way"
    assert screen == [{"type": "status", "requests": [{"lot_id": "L1", "stage": "on_the_way"}]}]


async def test_a_broken_screen_never_breaks_a_tool(api):
    from app.tools import get_quote

    async def broken(event):
        raise ConnectionError("socket gone")

    token = call_events.set(broken)
    try:
        api["reply"] = (200, {"price_per_tonne_rupees": 7000})
        assert (await get_quote("L1"))["price_per_tonne_rupees"] == 7000
    finally:
        call_events.reset(token)
