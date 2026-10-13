"""Twilio <-> Gemini Live audio conversion.

Input:  Twilio 8 kHz mu-law -> 16 kHz 16-bit PCM (Gemini Live input).
Output: Gemini Live 24 kHz 16-bit PCM -> 8 kHz mu-law (Twilio).
Pure functions so they are unit-testable. Python 3.12 has `audioop`; 3.13 needs `audioop-lts`.
"""


def mulaw8k_to_pcm16k(data: bytes) -> bytes:
    # TODO(F1)
    raise NotImplementedError


def pcm24k_to_mulaw8k(data: bytes) -> bytes:
    # TODO(F1)
    raise NotImplementedError
