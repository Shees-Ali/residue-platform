"""Live-transcript display text: each finished line romanised, plus its own script and language.

Callers may speak Urdu, Punjabi, Pashto, Sindhi or Saraiki, and Gemini Live's transcriptions come
back in whatever script it heard (sometimes Hindi or already Roman). A small, fast text model
names the line's language and rewrites it twice: in Roman script as people in Pakistan type it,
and in that language's own script. Display only: the stored transcript and the agent never depend
on it, so any failure returns None.
"""
import asyncio
import json
import logging
import os

from google import genai
from google.genai import types

log = logging.getLogger(__name__)

# Fast text models, tried in order: Gemini often answers 503 "high demand" for a moment.
MODELS = [
    m.strip()
    for m in os.getenv(
        "ROMAN_URDU_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.1-flash-lite"
    ).split(",")
    if m.strip()
]
TIMEOUT_S = 6.0

# Languages the call page labels; anything else is shown as "other".
LANGUAGES = {"ur", "pa", "ps", "sd", "skr", "en"}

PROMPT = (
    "This is one line from a phone call between a farmer in Punjab, Pakistan and a voice agent, "
    "transcribed by speech recognition in whatever script it heard. The language may be Urdu, "
    "Punjabi, Pashto, Sindhi, Saraiki or English, or a mix. Do not translate or add anything. "
    'Reply with JSON only: {"lang": "...", "roman": "...", "script": "..."} where "lang" is the '
    'main language: "ur" Urdu, "pa" Punjabi, "ps" Pashto, "sd" Sindhi, "skr" Saraiki, "en" '
    'English, or "other"; "roman" is the line in Roman script as people in Pakistan text it '
    "(e.g. Urdu 'Gandum ka bhoosa hai, do ton', Punjabi 'Kanak di toori ae'); \"script\" is the "
    "line in that language's own script (Urdu script; Shahmukhi for Punjabi and Saraiki; Pashto "
    "script; Sindhi script), or empty for English. Keep numbers, names and English words as "
    "spoken.\n\nLine: "
)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()  # GEMINI_API_KEY / GOOGLE_API_KEY from the environment
    return _client


async def romanize(text: str) -> dict[str, str] | None:
    """{"roman", "lang", maybe "script"} for one transcript line, or None if not done in time."""
    if not text.strip():
        return None
    try:
        async with asyncio.timeout(TIMEOUT_S):  # one budget for every model tried
            result = await _first_answer(PROMPT + text.strip())
    except TimeoutError:
        result = None
    if result is None:  # the line just stays as transcribed
        log.warning("Transcript romanisation failed for every model")
    return result


async def _first_answer(prompt: str) -> dict[str, str] | None:
    for model in MODELS:
        try:
            response = await _get_client().aio.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0
                ),
            )
            forms = _forms(json.loads(response.text or ""))
        except Exception as exc:  # 503 high demand, quota, bad JSON: try the next model
            log.info("Romanisation via %s failed: %s", model, exc)
            continue
        if forms:
            return forms
        log.info("Romanisation via %s: unusable answer", model)
    return None


def _forms(result: object) -> dict[str, str] | None:
    """The usable part of a model's answer: a non-empty "roman", the language ("other" when
    unknown) and the script line when there is one."""
    if not isinstance(result, dict):
        return None
    roman = result.get("roman")
    if not isinstance(roman, str) or not roman.strip():
        return None
    lang = result.get("lang")
    lang = lang.strip().lower() if isinstance(lang, str) else None  # e.g. a list for a mix
    forms = {"roman": roman.strip(), "lang": lang if lang in LANGUAGES else "other"}
    script = result.get("script")
    if isinstance(script, str) and script.strip():
        forms["script"] = script.strip()
    return forms
