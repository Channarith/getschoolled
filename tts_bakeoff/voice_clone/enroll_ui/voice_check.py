"""Optional pronunciation check: speech recognition on each recorded line, compared with the script it was meant to read.

Warn-only. Recognizers are imperfect, especially for colloquial Cantonese (they often write standard Chinese: 嘅 -> 的), so a
failed line asks the speaker to re-read it and never blocks enrollment. Skipped without error when no recognizer is installed.
Set ENROLL_ASR=off to disable, or ENROLL_ASR=<spec> (faster-whisper:large-v3, whisper:large-v3, fake:0) to choose the engine.
"""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

PASS_CER = {"default": 0.35, "yue": 0.45, "zh": 0.40, "km": 0.50}
_PUNCT = re.compile(r"[\s　，。、；：？！“”‘’「」『』（）()《》〈〉·…—\-.,;:?!\"'`~]+")


def normalize(text: str, lang: str = "en") -> str:
    t = unicodedata.normalize("NFKC", text or "").casefold()
    t = _PUNCT.sub("", t)
    if lang in ("yue", "zh"):
        try:  # fold simplified/traditional so a recognizer's script choice does not count as an error
            import opencc

            t = opencc.OpenCC("t2s").convert(t)
        except Exception:  # noqa: BLE001 - optional
            pass
    return t


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str, lang: str = "en") -> float:
    ref, hyp = normalize(reference, lang), normalize(hypothesis, lang)
    if not ref:
        return 0.0 if not hyp else 1.0
    return round(edit_distance(ref, hyp) / len(ref), 3)


def get_engine():
    """An ASR engine from tts_bakeoff.asr, or None when none is installed or ENROLL_ASR=off."""
    spec = os.environ.get("ENROLL_ASR", "auto-whisper")
    if spec == "off":
        return None
    from tts_bakeoff import asr

    if spec != "auto-whisper":
        return asr.get(spec, os.environ.get("AOEP_ASR_DEVICE", "auto"))
    for module, ctor in (("faster_whisper", lambda: asr.FasterWhisperASR(device=os.environ.get("AOEP_ASR_DEVICE", "auto"))),
                         ("whisper", lambda: asr.OpenAIWhisperASR())):
        try:
            __import__(module)
        except ImportError:
            continue
        return ctor()
    return None


def check_takes(takes: list[tuple[str, str, Path]], lang: str, engine=None) -> dict:
    """takes: (prompt id, script text, wav path). Returns per-line CER and pass/fail plus an overall summary."""
    engine = engine if engine is not None else get_engine()
    if engine is None:
        return {"available": False, "items": [], "warnings": 0}
    limit = PASS_CER.get(lang, PASS_CER["default"])
    items = []
    for pid, text, wav in takes:
        try:
            heard = engine.transcribe(str(wav), lang, reference=text)
        except Exception as exc:  # noqa: BLE001 - a recognizer failure must not break enrollment
            items.append({"id": pid, "error": f"{type(exc).__name__}: {str(exc)[:120]}", "pass": None})
            continue
        c = cer(text, heard, lang)
        items.append({"id": pid, "cer": c, "pass": c <= limit, "heard": heard})
    return {"available": True, "engine": getattr(engine, "name", "asr"), "limit": limit, "items": items,
            "warnings": sum(1 for i in items if i.get("pass") is False)}
