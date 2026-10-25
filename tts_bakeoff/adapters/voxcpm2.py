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

import gc
import inspect
import os
import re
from pathlib import Path

from .base import Adapter, write_wav

# An 8 GB card (Kal-el reports 7.52 GiB) finishes a short line and runs out of memory
# once the line is a paragraph. Stay at or under the length that already succeeded there.
TIGHT_VRAM_BYTES = 11 * 1024 ** 3
TIGHT_CHUNK_CHARS = 80
_SENTENCE_BREAK = re.compile(r"(?<=[\.\!\?\u3002\uFF01\uFF1F\u0964])\s+")
_CLAUSE_BREAK = re.compile(r"(?<=[,;:\uFF0C\u3001])\s+")


def _cuda_total_bytes() -> int | None:
    try:
        import torch
    except Exception:  # noqa: BLE001 - no torch means we are not on the render machine
        return None
    cuda = getattr(torch, "cuda", None)
    if cuda is None or not cuda.is_available():
        return None
    try:
        return int(cuda.get_device_properties(0).total_memory)
    except Exception:  # noqa: BLE001
        return None


def release_cuda() -> None:
    """Drop leftover generation buffers so the next line can allocate."""
    gc.collect()
    try:
        import torch
    except Exception:  # noqa: BLE001
        return
    cuda = getattr(torch, "cuda", None)
    if cuda is not None and cuda.is_available():
        cuda.empty_cache()


def is_oom(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "out of memory" in msg


def chunk_limit(options: dict | None = None, total_bytes: int | None = None) -> int:
    """Max characters per generate() call. 0 means speak the whole line at once.

    Under 11 GiB the whole paragraph does not fit beside the loaded model, so the
    line is spoken in the short pieces that already succeed on that card.
    ``chunk_chars`` or VOXCPM_CHUNK_CHARS overrides the measurement.
    """
    options = options or {}
    raw = options.get("chunk_chars")
    if raw is None:
        raw = os.environ.get("VOXCPM_CHUNK_CHARS")
    if raw is not None and str(raw) != "":
        return max(0, int(raw))
    if total_bytes is None:
        total_bytes = _cuda_total_bytes()
    if total_bytes is not None and total_bytes < TIGHT_VRAM_BYTES:
        return TIGHT_CHUNK_CHARS
    return 0


def split_text(text: str, limit: int) -> list[str]:
    """Break ``text`` into pieces of at most ``limit`` characters. ``limit`` <= 0 keeps it whole."""
    text = " ".join((text or "").split())
    if not text:
        return []
    if limit <= 0 or len(text) <= limit:
        return [text]
    return _pack(_pieces(text), limit)


def _pieces(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_BREAK.split(text) if p.strip()]
    if len(parts) > 1:
        return parts
    clauses = [p.strip() for p in _CLAUSE_BREAK.split(text) if p.strip()]
    if len(clauses) > 1:
        return clauses
    words = text.split(" ")
    return words if len(words) > 1 else [text]


def _pack(parts: list[str], limit: int) -> list[str]:
    out: list[str] = []
    buf = ""
    for part in parts:
        if len(part) > limit:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_hard(part, limit))
            continue
        if not buf:
            buf = part
        elif len(buf) + 1 + len(part) <= limit:
            buf = f"{buf} {part}"
        else:
            out.append(buf)
            buf = part
    if buf:
        out.append(buf)
    return out


def _hard(text: str, limit: int) -> list[str]:
    words = text.split(" ")
    if len(words) > 1:
        return _pack(words, limit)
    return [text[i:i + limit] for i in range(0, len(text), limit)] or [text]


def _join_wavs(wavs: list, rate: int):
    import numpy as np

    parts = [np.asarray(w).reshape(-1) for w in wavs]
    if len(parts) == 1:
        return parts[0]
    gap = np.zeros(max(1, int(rate * 0.04)), dtype=parts[0].dtype)
    joined: list = []
    for i, part in enumerate(parts):
        if i:
            joined.append(gap)
        joined.append(part)
    return np.concatenate(joined)


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

    def _piece_limit(self) -> int:
        """Characters of spoken text per generate() call. 0 keeps the line whole."""
        if getattr(self, "_chunk", None) is None:
            limit = chunk_limit(self.options)
            self._chunk = max(24, limit - self._prefix_len()) if limit else 0
        return self._chunk

    def _prefix_len(self) -> int:
        design = (self.options.get("design") or "").strip()
        style = (self.options.get("style") or "").strip()
        if design and not self.options.get("reference_wav"):
            return len(design) + 2
        if style and self.options.get("reference_wav"):
            return len(style) + 2
        return 0

    def _kwargs(self, spoken: str, model) -> tuple[dict, str]:
        kwargs = {
            "text": spoken,
            "cfg_value": float(self.options.get("cfg_value", 2.0)),
            "inference_timesteps": int(self.options.get("inference_timesteps", 10)),
        }
        ref = self.options.get("reference_wav")
        design = (self.options.get("design") or "").strip()
        mode = self.options.get("ref_mode") or ("reference" if self.options.get("style") else "continue")
        if mode not in ("continue", "reference"):
            raise ValueError(f"ref_mode must be 'continue' or 'reference', not {mode!r}")
        if design and not ref:
            kwargs["text"] = f"({design}){spoken}"   # voice design: the description replaces the reference
            mode = "design"
        elif self.options.get("style") and ref:
            kwargs["text"] = f"({self.options['style']}){spoken}"
            kwargs["reference_wav_path"] = ref
            mode = "reference"
        elif ref and mode == "reference":
            kwargs["reference_wav_path"] = ref
        elif ref:
            kwargs["prompt_wav_path"] = ref
            kwargs["prompt_text"] = self.options.get("reference_text", "")
        else:
            mode = "none"
        seed = self.options.get("seed")
        if seed is not None:
            if self._accepts_seed(model):
                kwargs["seed"] = int(seed)
            elif not getattr(self, "_seed_noted", False):
                self._seed_noted = True
                print("[voxcpm2] this voxcpm build has no seed argument: seed ignored", flush=True)
        return kwargs, mode

    def _generate(self, model, spoken: str, depth: int = 0):
        kwargs, mode = self._kwargs(spoken, model)
        self.last_mode = mode
        try:
            return model.generate(**kwargs)
        except Exception as exc:
            if depth >= 5 or not is_oom(exc):
                raise
            smaller = split_text(spoken, max(24, len(" ".join(spoken.split())) // 2))
            if len(smaller) < 2:
                raise
            release_cuda()
            print(f"[voxcpm2] out of memory on {len(spoken)} chars, retrying as {len(smaller)} pieces", flush=True)
            return _join_wavs([self._generate(model, part, depth + 1) for part in smaller], self._rate(model))

    @staticmethod
    def _rate(model) -> int:
        return int(getattr(getattr(model, "tts_model", model), "sample_rate", 48000))

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        model = self._model or self.load()
        pieces = split_text(text, self._piece_limit()) or [text]
        if len(pieces) > 1:
            print(f"[voxcpm2] speaking {len(text)} chars as {len(pieces)} pieces so it fits in GPU memory", flush=True)
            release_cuda()
        ref = self.options.get("reference_wav")
        _, mode = self._kwargs(pieces[0], model)
        print(f"[voxcpm2] ref-mode={mode} lang={lang} reference={Path(ref).name if ref else '-'}", flush=True)
        wavs = [self._generate(model, piece) for piece in pieces]
        rate = self._rate(model)
        write_wav(out_wav, _join_wavs(wavs, rate), rate)
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
