"""VoxCPM2 (OpenBMB), Apache-2.0, 30 languages including Khmer, Thai, Vietnamese, Swahili, Hindi, plus Chinese dialects (Cantonese listed).

Written from the VoxCPM README usage; NOT run against the real weights here. Needs Python 3.10-3.12,
torch >= 2.5 and CUDA >= 12 (or Apple MPS). Options: model_id (default openbmb/VoxCPM2),
cfg_value (2.0), inference_timesteps (10), reference_wav + reference_text (optional cloning), style (optional).

style: a short description such as "cute, sweet, bright voice". Per the model card's "controllable cloning" it is put in
parentheses before the text and the reference audio is given as reference_wav_path only (no prompt text: with the
transcript the model continues the prompt, "ultimate cloning", and does not take style guidance). Not run against the
real weights; compare against the post-processing tones by ear.

ref_mode (option): "continue" gives the model the reference audio AND its exact transcript, which it continues ("ultimate cloning"): best
when the target language is the reference's language and the transcript is exactly what was said. "reference" gives the audio only
(reference_wav_path, no prompt text): use it across languages, or when the transcript is not trustworthy; the voice carries over, the
words come only from the text. A transcript that does not match the audio in continue mode is what produces the model's
'Badcase detected, audio_text_ratio=...' retries and speech that does not follow the text. Default (no ref_mode): continue, or
reference when a style is set. The mode used is logged and returned as ref_mode.
"""
from __future__ import annotations

from pathlib import Path

from .base import Adapter, write_wav


class VoxCPM2Adapter(Adapter):
    name = "voxcpm2"
    languages = {"en", "es", "zh", "yue", "vi", "th", "km", "sw", "hi"}  # yue: listed under "Chinese Dialect" on the model card; text written in Cantonese, no language tag
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
        ref = self.options.get("reference_wav")
        mode = self.options.get("ref_mode") or ("reference" if self.options.get("style") else "continue")
        if mode not in ("continue", "reference"):
            raise ValueError(f"ref_mode must be 'continue' or 'reference', not {mode!r}")
        if self.options.get("style") and ref:
            kwargs["text"] = f"({self.options['style']}){text}"
            kwargs["reference_wav_path"] = ref
            mode = "reference"
        elif ref and mode == "reference":
            kwargs["reference_wav_path"] = ref
        elif ref:
            kwargs["prompt_wav_path"] = ref
            kwargs["prompt_text"] = self.options.get("reference_text", "")
        else:
            mode = "none"
        self.last_mode = mode
        print(f"[voxcpm2] ref-mode={mode} lang={lang} reference={Path(ref).name if ref else '-'}", flush=True)
        wav = model.generate(**kwargs)
        rate = int(getattr(getattr(model, "tts_model", model), "sample_rate", 48000))
        write_wav(out_wav, wav, rate)
        return rate

    def synthesize(self, text, lang, out_wav):
        info = super().synthesize(text, lang, out_wav)
        info["ref_mode"] = getattr(self, "last_mode", None)
        return info
