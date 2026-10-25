"""VoxCPM2 (OpenBMB), Apache-2.0, 30 languages including Khmer, Thai, Vietnamese, Swahili, Hindi, plus Chinese dialects (Cantonese listed).

Written from the VoxCPM README usage; NOT run against the real weights here. Needs Python 3.10-3.12,
torch >= 2.5 and CUDA >= 12 (or Apple MPS). Options: model_id (default openbmb/VoxCPM2),
cfg_value (2.0), inference_timesteps (10), reference_wav + reference_text (optional cloning), style (optional).

style: a short description such as "cute, sweet, bright voice". Per the model card's "controllable cloning" it is put in
parentheses before the text and the reference audio is given as reference_wav_path only (no prompt text: with the
transcript the model continues the prompt, "ultimate cloning", and does not take style guidance). Not run against the
real weights; compare against the post-processing tones by ear.

design (option): VOICE DESIGN, no reference audio at all. Per the model card ("(A young woman, gentle and sweet voice)Hello, ...") the
description goes in parentheses at the start of the text and the model invents a voice that fits it. The card warns that "Voice Design and
Controllable Voice Cloning results can vary between runs", so a designed voice is only reproducible if it is frozen: design it once with a
fixed seed, keep the generated clip as a reference wav, and clone from that (tts_bakeoff/voice_design). seed (option): passed to generate()
when the installed voxcpm accepts a seed argument (the project README shows seed=42); otherwise it is dropped and logged, not an error.

ref_mode (option): "continue" gives the model the reference audio AND its exact transcript, which it continues ("ultimate cloning"): best
when the target language is the reference's language and the transcript is exactly what was said. "reference" gives the audio only
(reference_wav_path, no prompt text): use it across languages, or when the transcript is not trustworthy; the voice carries over, the
words come only from the text. A transcript that does not match the audio in continue mode is what produces the model's
'Badcase detected, audio_text_ratio=...' retries and speech that does not follow the text. Default (no ref_mode): continue, or
reference when a style is set. The mode used is logged and returned as ref_mode.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from .base import Adapter, write_wav


class VoxCPM2Adapter(Adapter):
    name = "voxcpm2"
    # The model card (huggingface.co/openbmb/VoxCPM2, read 2026-10-25) lists 30 languages and "no language tag needed": ar, my (Burmese), zh, da, nl, en,
    # fi, fr, de, el, he, hi, id, it, ja, km, ko, lo, ms, no (our code nb), pl, pt, ru, es, sw, sv, tl (our code fil), th, tr, vi; plus Chinese dialects
    # incl. Cantonese (yue). Quality varies with each language's training data (the card says so), so judge each one by ear.
    languages = {"ar", "my", "zh", "da", "nl", "en", "fi", "fr", "de", "el", "he", "hi", "id", "it", "ja", "km", "ko", "lo", "ms", "nb", "pl", "pt", "ru",
                 "es", "sw", "sv", "fil", "th", "tr", "vi", "yue"}
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
        design = (self.options.get("design") or "").strip()
        mode = self.options.get("ref_mode") or ("reference" if self.options.get("style") else "continue")
        if mode not in ("continue", "reference"):
            raise ValueError(f"ref_mode must be 'continue' or 'reference', not {mode!r}")
        if design and not ref:
            kwargs["text"] = f"({design}){text}"   # voice design: the description replaces the reference
            mode = "design"
        elif self.options.get("style") and ref:
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
        seed = self.options.get("seed")
        if seed is not None:
            if self._accepts_seed(model):
                kwargs["seed"] = int(seed)
            else:
                print("[voxcpm2] this voxcpm build has no seed argument: seed ignored", flush=True)
        wav = model.generate(**kwargs)
        rate = int(getattr(getattr(model, "tts_model", model), "sample_rate", 48000))
        write_wav(out_wav, wav, rate)
        return rate

    @staticmethod
    def _accepts_seed(model) -> bool:
        try:
            params = inspect.signature(model.generate).parameters
        except (TypeError, ValueError):
            return False
        return "seed" in params

    def synthesize(self, text, lang, out_wav):
        info = super().synthesize(text, lang, out_wav)
        info["ref_mode"] = getattr(self, "last_mode", None)
        return info
