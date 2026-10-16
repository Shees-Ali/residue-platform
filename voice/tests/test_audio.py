import array
import audioop
import math

from app.audio import ToLine, from_line


def _sine(rate: int, ms: int, hz: float, amp: int = 8000) -> bytes:
    n = rate * ms // 1000
    return array.array(
        "h", (int(amp * math.sin(2 * math.pi * hz * i / rate)) for i in range(n))
    ).tobytes()


def _stream(converter: ToLine, data: bytes, size: int) -> bytes:
    """Feed one converter chunk by chunk, as a call does."""
    return b"".join(converter.convert(data[i : i + size]) for i in range(0, len(data), size))


def _zero_crossings_hz(pcm: bytes, rate: int) -> float:
    s = array.array("h", pcm)
    crossings = sum(1 for a, b in zip(s, s[1:], strict=False) if (a < 0) != (b < 0))
    return crossings / 2 / (len(s) / rate)


def test_line_audio_is_little_endian_l16_like_gemini():
    sample = array.array("h", [1000]).tobytes()  # little-endian on every target
    assert from_line(sample) == sample
    assert from_line(b"\x01\x02\x03") == b"\x01\x02"  # a stray odd byte is dropped
    out = ToLine().convert(array.array("h", [12000] * 2400).tobytes())  # 100 ms of DC
    assert array.array("h", out)[-1] > 10000  # read little-endian: still a large positive value


def test_round_trip_keeps_pitch_and_level():
    tone = _sine(24000, 500, 1000)
    line = _stream(ToLine(), tone, 960)
    assert abs(len(line) // 2 - 8000) <= 2  # 16 kHz
    back = from_line(line)
    assert abs(_zero_crossings_hz(back, 16000) - 1000) < 30
    steady = back[len(back) // 4 // 2 * 2 :]  # skip filter start-up, whole samples
    assert abs(audioop.rms(steady, 2) / audioop.rms(tone, 2) - 1) < 0.1


def test_anti_alias_removes_tones_that_would_fold():
    back = from_line(ToLine().convert(_sine(24000, 500, 11000)))[1600:]  # skip start-up
    assert audioop.rms(back, 2) < 8000 * 0.707 * 0.1  # >= 20 dB down instead of folding to 5 kHz


def test_chunked_equals_one_shot_and_odd_chunks_are_carried():
    tone = _sine(24000, 200, 440)
    one_shot = ToLine().convert(tone)
    assert _stream(ToLine(), tone, 960) == one_shot
    assert _stream(ToLine(), tone, 961) == one_shot
