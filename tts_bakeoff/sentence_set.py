"""The 10-sentence listening set for every platform and extra language, and the checks a sentence file must pass.

The 8 languages with the full 40-sentence set (en es zh vi th km sw hi) reuse their rows exactly (first 10 ids of SET10 from
sentences/<lang>.jsonl). Every other language has its own sentences/<lang>.jsonl with just these 10 ids, machine translated
from the English row by translate_sentences.py (source 'grok-translation-v1', review_status 'unreviewed').
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from .build_sentences import OUT
from .sentences_master import LANGS

SET10 = ("S01", "M01", "L01", "N01", "D01", "P01", "V01", "Q01", "S02", "M02")
FULL_SET_LANGS = frozenset(LANGS)
SOURCE = "grok-translation-v1"
EXPECT_DIGITS = {"N01": "25", "D01": "5", "P01": "2", "M02": "3"}  # if a translation writes digits they must be these

_SCRIPT_RANGES = {  # scripts translation_validate does not know
    "my": [(0x1000, 0x109F), (0xAA60, 0xAA7F)], "lo": [(0x0E80, 0x0EFF)], "ta": [(0x0B80, 0x0BFF)], "te": [(0x0C00, 0x0C7F)],
    "ne": [(0x0900, 0x097F)], "mr": [(0x0900, 0x097F)], "si": [(0x0D80, 0x0DFF)], "gu": [(0x0A80, 0x0AFF)],
    "kn": [(0x0C80, 0x0CFF)], "ml": [(0x0D00, 0x0D7F)], "pa": [(0x0A00, 0x0A7F)], "am": [(0x1200, 0x139F)],
    "ka": [(0x10A0, 0x10FF), (0x2D00, 0x2D2F), (0x1C90, 0x1CBF)], "ps": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "bg": [(0x0400, 0x04FF)], "mk": [(0x0400, 0x04FF)], "kk": [(0x0400, 0x04FF)], "mn": [(0x0400, 0x04FF)],
    "sr": [(0x0400, 0x04FF), (0x0041, 0x024F)], "yue": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],
}


def path_for(lang: str) -> Path:
    return OUT / f"{lang}.jsonl"


def load10(lang: str) -> list[dict]:
    rows = {}
    for line in path_for(lang).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["id"]] = row
    return [rows[i] for i in SET10 if i in rows]


def script_fraction(text: str, lang: str) -> float | None:
    """Share of letters in the script the language is written in (None = too short to tell)."""
    from aoep_shared.translation_validate import _RANGES

    letters = [c for c in text if unicodedata.category(c)[0] in ("L", "M")]
    if len(letters) < 3:
        return None
    ranges = _SCRIPT_RANGES.get(lang) or _RANGES.get(lang)
    if ranges:
        return sum(1 for c in letters if any(lo <= ord(c) <= hi for lo, hi in ranges)) / len(letters)
    return sum(1 for c in letters if "LATIN" in unicodedata.name(c, "")) / len(letters)


def problems(lang: str, row: dict, ref_en: str) -> list[str]:
    """Why a sentence is not acceptable (empty list = fine). Used on fresh Grok output and by the tests."""
    from aoep_shared.translation_validate import _MARKUP, _RANGES, has_loop, numbers_in, unchanged_from_source

    text = str(row.get("text", "")).strip()
    out = []
    if not text:
        return ["empty"]
    if _MARKUP.search(text) or "\n" in text:
        out.append("markup or newline")
    if has_loop(text):
        out.append("loop")
    frac = script_fraction(text, lang)
    need = 0.5 if (lang in _SCRIPT_RANGES or lang in _RANGES) else 0.8
    if row.get("id") == "P01":
        need = min(need, 0.35)  # the name sentence may legitimately keep the person's Latin-script name
    if frac is not None and frac < need:
        out.append(f"wrong script ({frac:.2f})")
    if lang != "en" and len(ref_en.split()) >= 4 and unchanged_from_source(ref_en, text):
        out.append("unchanged from English")
    want = EXPECT_DIGITS.get(row.get("id", ""))
    found = numbers_in(text)
    if want and found and want not in found:
        out.append(f"number {found} is not {want}")
    return out
