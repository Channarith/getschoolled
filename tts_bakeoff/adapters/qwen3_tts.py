"""Qwen3-TTS (Alibaba Qwen), Apache-2.0 weights, 10 languages (no km/vi/th/sw/hi).

Written from the public model card style usage; NOT run against the real weights here. Options:
model_id (default Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice), speaker (default "Ryan").
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav

LANGUAGE_NAMES = {"en": "English", "zh": "Chinese", "es": "Spanish"}


class Qwen3TTSAdapter(Adapter):
    name = "qwen3_tts"
    languages = set(LANGUAGE_NAMES)
    requires = ("qwen_tts", "torch")

    def load(self):
        import torch
        from qwen_tts import Qwen3TTSModel

        device = self.options.get("device", "cuda:0" if torch.cuda.is_available() else "cpu")
        self._model = Qwen3TTSModel.from_pretrained(
            self.options.get("model_id", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"),
            device_map=device,
            dtype=torch.bfloat16 if device != "cpu" else torch.float32,
        )
        return self._model

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        model = self._model or self.load()
        wavs, rate = model.generate_custom_voice(
            text=text,
            language=LANGUAGE_NAMES[lang],
            speaker=self.options.get("speaker", "Ryan"),
        )
        write_wav(out_wav, wavs[0], int(rate))
        return int(rate)
