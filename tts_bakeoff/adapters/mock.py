"""TTS-free adapter for tests and dry runs: writes a tone whose length follows the text length.

The tone is a deterministic sine burst per character, so durations, silence and clipping checks and
the whole runner/report pipeline can be exercised on any machine with only numpy.
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav

SAMPLE_RATE = 16000
SECONDS_PER_CHAR = 0.06


class MockAdapter(Adapter):
    name = "mock"
    languages = {"en", "es", "zh", "vi", "th", "km", "sw", "hi", "bn"}
    requires = ("numpy",)

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import numpy as np

        n = max(1, int(len(text) * SECONDS_PER_CHAR * SAMPLE_RATE))
        t = np.arange(n) / SAMPLE_RATE
        freq = 180.0 + (sum(ord(c) for c in text) % 120)
        samples = 0.3 * np.sin(2 * np.pi * freq * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3.0 * t))
        write_wav(out_wav, samples, SAMPLE_RATE)
        return SAMPLE_RATE
