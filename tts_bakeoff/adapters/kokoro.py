"""Kokoro-82M (hexgrad), Apache-2.0 weights, fixed voices, no cloning. Runs on CPU.

Written from the Kokoro README usage; NOT run against the real weights here. Language codes there:
a (US English), e (Spanish), z (Mandarin), h (Hindi). Options: voices (dict lang -> voice name).
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav

KOKORO_LANG = {"en": "a", "es": "e", "zh": "z", "hi": "h"}
DEFAULT_VOICE = {"en": "af_heart", "es": "ef_dora", "zh": "zf_xiaobei", "hi": "hf_alpha"}


class KokoroAdapter(Adapter):
    name = "kokoro"
    languages = set(KOKORO_LANG)
    requires = ("kokoro", "numpy")

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import numpy as np
        from kokoro import KPipeline

        self._model = self._model or {}
        pipe = self._model.get(lang) or self._model.setdefault(lang, KPipeline(lang_code=KOKORO_LANG[lang]))
        voice = (self.options.get("voices") or {}).get(lang, DEFAULT_VOICE[lang])
        chunks = [np.asarray(audio) for _, _, audio in pipe(text, voice=voice)]
        write_wav(out_wav, np.concatenate(chunks) if chunks else np.zeros(1), 24000)
        return 24000
