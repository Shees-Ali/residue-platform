"""Phone line <-> Gemini Live audio conversion (Telnyx media streams, L16 at 16 kHz).

Input:  Telnyx L16 16 kHz -> 16 kHz PCM16 (Gemini input): the same format, passed through.
Output: Gemini 24 kHz PCM16 -> anti-alias low-pass -> 16 kHz L16.
Telnyx sends L16 on the media WebSocket little-endian, unlike RFC 3551's network order for L16
RTP (Telnyx's reference integration, May 2026), which matches Gemini: no byte swapping.
`audioop` ships with 3.12; 3.13+ gets it from the `audioop-lts` package.
"""
import array
import audioop
import math


def _lowpass(fc: float, fs: float, q: float) -> tuple[float, ...]:
    """RBJ cookbook biquad low-pass, normalised (b0, b1, b2, a1, a2)."""
    w = 2 * math.pi * fc / fs
    alpha = math.sin(w) / (2 * q)
    a0 = 1 + alpha
    b1 = (1 - math.cos(w)) / a0
    return b1 / 2, b1, b1 / 2, -2 * math.cos(w) / a0, (1 - alpha) / a0


# 4th-order Butterworth at 6.5 kHz (two biquads): keeps speech up to the 8 kHz Nyquist of the
# 16 kHz line while 9-12 kHz energy is attenuated instead of folding into 4-7 kHz.
_ANTI_ALIAS = [_lowpass(6500, 24000, 0.5412), _lowpass(6500, 24000, 1.3066)]


def from_line(l16: bytes) -> bytes:
    """Caller audio from Telnyx (16 kHz L16, little-endian) -> Gemini input: whole samples only."""
    return l16[: len(l16) // 2 * 2]


class ToLine:
    """Gemini 24 kHz PCM16 -> 16 kHz L16, one per call. Tolerates odd-length chunks.

    Keeps resampler and filter state so 20 ms chunks join without clicks. On barge-in, build a
    new one, so no stale state or odd byte carries over.
    """

    def __init__(self) -> None:
        self._state = None
        self._carry = b""
        self._z = [[0.0, 0.0] for _ in _ANTI_ALIAS]

    def convert(self, pcm24k: bytes) -> bytes:
        data = self._carry + pcm24k
        whole = len(data) - len(data) % 2
        data, self._carry = data[:whole], data[whole:]
        samples = [float(s) for s in array.array("h", data)]
        for (b0, b1, b2, a1, a2), z in zip(_ANTI_ALIAS, self._z, strict=True):
            z1, z2 = z
            for i, x in enumerate(samples):  # direct form II transposed
                y = b0 * x + z1
                z1 = b1 * x - a1 * y + z2
                z2 = b2 * x - a2 * y
                samples[i] = y
            z[:] = z1, z2
        filtered = array.array("h", (max(-32768, min(32767, round(y))) for y in samples))
        pcm16k, self._state = audioop.ratecv(filtered.tobytes(), 2, 1, 24000, 16000, self._state)
        return pcm16k
