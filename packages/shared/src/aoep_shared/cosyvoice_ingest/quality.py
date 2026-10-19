"""Transcript checks before a clip is written into a CosyVoice recipe."""

from __future__ import annotations

import re
from collections import Counter


_KHMER = re.compile(r"[\u1780-\u17ff]")
_LATIN = re.compile(r"[A-Za-z]")


def transcript_reject_reason(text: str, language: str) -> str:
    """Return an empty string when ``text`` is usable for ``language``.

    Khmer training text must be mostly Khmer script. Latin hallucinations and
    a single word repeated across the clip are rejected. Other languages are
    accepted once the text is non-empty; the caller already dropped blanks.
    """
    raw = " ".join((text or "").split())
    if not raw:
        return "empty_transcript"
    lang = (language or "").strip().lower().replace("_", "-").split("-", 1)[0]
    if lang != "km":
        return ""
    km = len(_KHMER.findall(raw))
    latin = len(_LATIN.findall(raw))
    if km < 4:
        return "few_khmer_chars"
    if latin and km / float(km + latin) < 0.6:
        return "not_mostly_khmer"
    tokens = raw.split()
    if len(tokens) >= 6:
        word, count = Counter(tokens).most_common(1)[0]
        if count >= 4 and count / float(len(tokens)) >= 0.45 and len(word) <= 12:
            return "repetition"
    return ""
