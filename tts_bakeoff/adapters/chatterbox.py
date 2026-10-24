"""Chatterbox Multilingual (Resemble AI), MIT, 23 languages including Swahili and Hindi.

Written from the project README usage; NOT run against the real weights here. Output carries Resemble's
Perth watermark by default. Options: device (cuda|cpu|mps), audio_prompt (optional reference wav).
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav


class ChatterboxAdapter(Adapter):
    name = "chatterbox"
    languages = {"en", "es", "zh", "sw", "hi"}
    requires = ("chatterbox", "torch")

    def load(self):
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        device = self.options.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        return self._model

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        model = self._model or self.load()
        kwargs = {"language_id": lang}
        if self.options.get("audio_prompt"):
            kwargs["audio_prompt_path"] = self.options["audio_prompt"]
        wav = model.generate(text, **kwargs)
        rate = int(model.sr)
        write_wav(out_wav, wav.squeeze().cpu().numpy(), rate)
        return rate
