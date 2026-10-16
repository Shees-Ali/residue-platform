"""One live call, whatever the transport: API call record + ADK live session + transcript.

Transports (Twilio, browser) own the socket and audio format. They push caller audio into the
LiveRequestQueue and hand run_call two callbacks for the agent's audio and for barge-in.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import aclosing

from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app import api_client
from app.agent import intake_agent
from app.call_context import (
    CallEvents,
    call_events,
    current_call_id,
    current_transcript,
    emit,
    escalation_snapshots,
)
from app.roman import romanize

APP_NAME = "residue-voice"
USER_ID = "caller"  # ADK's per-user grouping is unused; the session id is the call id
AGENT_STOP_GRACE = 5.0  # seconds for ADK to wind down after the queue closes
RETRY_DELAY = 0.5
TRANSPORT_GRACE = 10.0  # seconds a transport waits for run_call after hanging up
ROMAN_RETRY_DELAY = 3.0  # seconds before retrying a failed romanisation
log = logging.getLogger(__name__)
_closing: set[asyncio.Task] = set()

runner = Runner(
    agent=intake_agent,
    app_name=APP_NAME,
    session_service=InMemorySessionService(),
    auto_create_session=True,
)

RUN_CONFIG = RunConfig(
    streaming_mode=StreamingMode.BIDI,
    response_modalities=[types.Modality.AUDIO],
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    # Survive Live API reconnects (GoAway, dropped socket) without losing the conversation,
    # and keep long calls under the context limit.
    session_resumption=types.SessionResumptionConfig(),
    context_window_compression=types.ContextWindowCompressionConfig(
        sliding_window=types.SlidingWindow()
    ),
)

SendAudio = Callable[[bytes], Awaitable[None]]  # 24 kHz 16-bit mono PCM from the agent
Interrupt = Callable[[], Awaitable[None]]  # caller barged in: drop queued agent audio


async def run_call(
    external_call_id: str,
    caller_phone: str,
    queue: LiveRequestQueue,
    send_audio: SendAudio,
    interrupt: Interrupt,
    *,
    kind: str = "intake",
    opening: str = "",
    on_event: CallEvents | None = None,
) -> None:
    """Open the call record, run the agent until the queue closes, then close the record.

    `external_call_id` is the carrier's id for the call (unique per call, at most 64 chars).
    `opening` is a text turn queued ahead of any caller audio (e.g. the job to verify), so the
    agent speaks first. Returns when the transport closes the queue or the live session ends;
    on return the transport should hang up its side.
    `on_event` receives live events for a screen (transcript lines, the saved lot, the quote);
    display only, see Transcript below.
    """
    # Queued first so it precedes any audio the transport pushes while start_call is in flight.
    queue.send_content(
        types.Content(role="user", parts=[types.Part(text=opening or "The caller has connected.")])
    )
    started = await api_client.start_call(external_call_id, caller_phone, kind)
    call_id = started.get("call_id")
    if not call_id:
        raise RuntimeError(f"API refused the call: {started.get('error', 'unknown')}")

    transcript: list[str] = []
    # Set before the agent task starts so it, and every task ADK spawns (tool calls included),
    # inherits them.
    tokens = (
        (current_call_id, current_call_id.set(call_id)),
        (current_transcript, current_transcript.set(transcript)),
        (escalation_snapshots, escalation_snapshots.set({})),
        (call_events, call_events.set(on_event)),
    )
    # The live loop runs in its own task: cancelling run_call never reaches ADK mid-cleanup.
    # Teardown (below) ends it by closing the queue, and cancels it once only if it hangs.
    agent = asyncio.create_task(_converse(call_id, queue, send_audio, interrupt, transcript))
    status = "failed"
    try:
        await asyncio.shield(agent)
        status = "completed"
    finally:
        queue.close()
        for var, token in reversed(tokens):
            var.reset(token)
        # One shielded task, held in _closing so it outlives a second cancellation of run_call.
        # It logs its own errors and never raises, so it cannot hide why the call ended.
        closing = asyncio.create_task(_close(agent, call_id, status, transcript))
        _closing.add(closing)
        closing.add_done_callback(_closing.discard)
        await asyncio.shield(closing)


async def stop_agent(agent: asyncio.Task, queue: LiveRequestQueue) -> BaseException | None:
    """For transports: end a run_call task and return its error, if any.

    Closing the queue lets the call finish normally; a call still running after TRANSPORT_GRACE
    is cancelled, and if its (shielded) teardown is still busy after another TRANSPORT_GRACE the
    transport stops waiting: the task finishes on its own, held here and logged if it fails.
    Either way the transport is released within 2 x TRANSPORT_GRACE.
    """
    queue.close()
    try:
        await asyncio.wait({agent}, timeout=TRANSPORT_GRACE)
    finally:
        if not agent.done():
            agent.cancel()
    await asyncio.wait({agent}, timeout=TRANSPORT_GRACE)
    if not agent.done():
        _closing.add(agent)
        agent.add_done_callback(_finish_detached)
        return None
    return None if agent.cancelled() else agent.exception()


def _finish_detached(task: asyncio.Task) -> None:
    _closing.discard(task)
    if not task.cancelled() and task.exception() is not None:
        log.error("detached call ended with an error", exc_info=task.exception())


async def _converse(
    call_id: str,
    queue: LiveRequestQueue,
    send_audio: SendAudio,
    interrupt: Interrupt,
    transcript: list[str],
) -> None:
    live = runner.run_live(
        user_id=USER_ID, session_id=call_id, live_request_queue=queue, run_config=RUN_CONFIG
    )
    live_lines = Transcript() if call_events.get() else None
    try:
        async with aclosing(live):  # ADK's cleanup finishes inside this task
            async for event in live:
                if event.interrupted:
                    await interrupt()
                for part in event.content.parts if event.content else []:
                    blob = part.inline_data
                    if blob and blob.data and (blob.mime_type or "").startswith("audio/pcm"):
                        await send_audio(blob.data)
                for who, t in (
                    ("caller", event.input_transcription),
                    ("agent", event.output_transcription),
                ):
                    if not (t and t.text):
                        continue
                    if t.finished:
                        transcript.append(f"{who}: {t.text.strip()}")
                    if live_lines:
                        await live_lines.heard(who, t.text, bool(t.finished))
                if live_lines and (event.turn_complete or event.interrupted):
                    await live_lines.end_agent_turn()  # never leave a turn "speaking"
    finally:
        if live_lines:
            await live_lines.close()


class Transcript:
    """Live transcript events for a screen. Each turn has an id: the agent's turn grows piece by
    piece (`final: false`) then is sent whole (`final: true`); the caller's arrives finished.
    Every finished line is then sent again romanised, with its language and its own script.

    `order` places a turn on screen. On Gemini 3.x the caller's line often arrives only after
    the agent has started answering it, so a caller line that lands during an open agent turn
    is ordered just before that turn."""

    def __init__(self) -> None:
        self._turns = 0
        self._agent_turn: int | None = None
        self._agent_text = ""
        self._romanizing: set[asyncio.Task] = set()

    async def heard(self, who: str, text: str, finished: bool) -> None:
        if who == "caller":
            if not finished:  # only non-3.x Live models send caller pieces; wait for the line
                return
            self._turns += 1
            turn = self._turns
            order = self._agent_turn - 0.5 if self._agent_turn is not None else turn
            await self._finished(turn, order, who, text)
            return
        if self._agent_turn is None:
            self._turns += 1
            self._agent_turn, self._agent_text = self._turns, ""
        turn = self._agent_turn
        if not finished:
            self._agent_text += text
            await emit(_line(turn, turn, who, self._agent_text, final=False))
            return
        # ADK's finished text is its own accumulation; after a Live reconnect it can be shorter
        # than what this screen already showed, so keep the longer one.
        whole = text if len(text.strip()) >= len(self._agent_text.strip()) else self._agent_text
        self._agent_turn, self._agent_text = None, ""
        await self._finished(turn, turn, who, whole)

    async def end_agent_turn(self) -> None:
        """Close an agent turn that never got a finished line (turn end, barge-in)."""
        if self._agent_turn is not None and self._agent_text.strip():
            await self.heard("agent", self._agent_text, True)
        self._agent_turn, self._agent_text = None, ""

    async def _finished(self, turn: int, order: float, who: str, text: str) -> None:
        await emit(_line(turn, order, who, text.strip(), final=True))
        task = asyncio.create_task(self._romanize(turn, text.strip()))
        self._romanizing.add(task)
        task.add_done_callback(self._romanizing.discard)

    async def _romanize(self, turn: int, text: str) -> None:
        forms = await romanize(text)
        if forms is None:  # Gemini's "high demand" 503s come in short bursts: try once more
            await asyncio.sleep(ROMAN_RETRY_DELAY)
            forms = await romanize(text)
        if forms:
            await emit({"type": "roman", "id": turn, **forms})

    async def close(self) -> None:
        """Cancel conversions still in flight and wait for them, so none outlives the call."""
        for task in self._romanizing:
            task.cancel()
        await asyncio.gather(*self._romanizing, return_exceptions=True)


def _line(turn: int, order: float, who: str, text: str, *, final: bool) -> dict:
    return {
        "type": "transcript",
        "id": turn,
        "order": order,
        "who": who,
        "text": text,
        "final": final,
    }


async def _close(agent: asyncio.Task, call_id: str, status: str, transcript: list[str]) -> None:
    """Let ADK finish (closed queue), drop its session, then close the call record."""
    await asyncio.wait({agent}, timeout=AGENT_STOP_GRACE)
    if not agent.done():  # stuck, e.g. in send_audio on a dead socket
        agent.cancel()
    try:
        await agent
    except asyncio.CancelledError:
        pass
    except Exception:  # also raised by run_call, unless run_call was cancelled first
        log.warning("agent for call %s ended with an error", call_id, exc_info=True)
    try:
        await runner.session_service.delete_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=call_id
        )
    except Exception:
        log.exception("could not drop ADK session %s", call_id)
    error = ""
    for attempt in range(3):  # retried: the transcript only exists here until it is saved
        try:
            result = await api_client.end_call(call_id, status, "\n".join(transcript))
        except Exception as exc:  # e.g. the ID token fetch failed
            error = repr(exc)
        else:
            if "error" not in result:
                return
            error = result["error"]
            if error.startswith("http_4"):  # the API rejected it; retrying will not help
                break
        if attempt < 2:
            await asyncio.sleep(RETRY_DELAY * 2**attempt)
    log.error("could not close call %s: %s", call_id, error)
