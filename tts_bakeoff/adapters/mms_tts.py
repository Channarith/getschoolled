"""MMS-TTS (Meta), one small VITS checkpoint per language. Reference baseline, NOT SHIPPABLE (CC-BY-NC).

Uses the transformers VitsModel API. Only the Khmer card was read for its license; the other
checkpoints are assumed to share the family license. Runs on CPU. Options: device.
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav

CHECKPOINT = {
    "km": "facebook/mms-tts-khm",
    "vi": "facebook/mms-tts-vie",
    "th": "facebook/mms-tts-tha",
    "sw": "facebook/mms-tts-swh",
    "hi": "facebook/mms-tts-hin",
    "es": "facebook/mms-tts-spa",
    "en": "facebook/mms-tts-eng",
}


class MmsTtsAdapter(Adapter):
    name = "mms_tts"
    languages = set(CHECKPOINT)
    requires = ("transformers", "torch")

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import torch
        from transformers import AutoTokenizer, VitsModel

        self._model = self._model or {}
        if lang not in self._model:
            tok = AutoTokenizer.from_pretrained(CHECKPOINT[lang])
            model = VitsModel.from_pretrained(CHECKPOINT[lang]).to(self.options.get("device", "cpu"))
            self._model[lang] = (tok, model)
        tok, model = self._model[lang]
        inputs = tok(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            wav = model(**inputs).waveform[0].cpu().numpy()
        rate = int(model.config.sampling_rate)
        write_wav(out_wav, wav, rate)
        return rate
