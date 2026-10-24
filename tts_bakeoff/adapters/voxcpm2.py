"""VoxCPM2 (OpenBMB), Apache-2.0, 30 languages including Khmer, Thai, Vietnamese, Swahili, Hindi.

Written from the VoxCPM README usage; NOT run against the real weights here. Needs Python 3.10-3.12,
torch >= 2.5 and CUDA >= 12 (or Apple MPS). Options: model_id (default openbmb/VoxCPM2),
cfg_value (2.0), inference_timesteps (10), reference_wav + reference_text (optional cloning).
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav


class VoxCPM2Adapter(Adapter):
    name = "voxcpm2"
    languages = {"en", "es", "zh", "vi", "th", "km", "sw", "hi"}
    requires = ("voxcpm",)

    def load(self):
        from voxcpm import VoxCPM

        self._model = VoxCPM.from_pretrained(self.options.get("model_id", "openbmb/VoxCPM2"))
        return self._model

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        model = self._model or self.load()
        kwargs = {
            "text": text,
            "cfg_value": float(self.options.get("cfg_value", 2.0)),
            "inference_timesteps": int(self.options.get("inference_timesteps", 10)),
        }
        if self.options.get("reference_wav"):
            kwargs["prompt_wav_path"] = self.options["reference_wav"]
            kwargs["prompt_text"] = self.options.get("reference_text", "")
        wav = model.generate(**kwargs)
        rate = int(getattr(getattr(model, "tts_model", model), "sample_rate", 48000))
        write_wav(out_wav, wav, rate)
        return rate
