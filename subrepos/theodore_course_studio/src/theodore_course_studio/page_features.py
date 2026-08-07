"""Offline page feature extraction for quality scoring (no network / no LLM)."""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")
_STOP = frozenset(
    """
    the and for that with this from have were been they their will would
    about into when what which there your could should does are was not
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "") if w.lower() not in _STOP]


def page_features(title: str, body: str) -> dict[str, float]:
    """Dense, offline-computable signals used by the quality model."""
    text = f"{title or ''}\n{body or ''}".strip()
    words = tokenize(text)
    chars = len(text)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", body or "") if s.strip()]
    lines = [ln for ln in (body or "").splitlines() if ln.strip()]
    bullets = sum(1 for ln in lines if re.match(r"^[\-\*\u2022\d]+[\.\)]\s", ln.strip()))
    avg_word = (sum(len(w) for w in words) / len(words)) if words else 0.0
    unique = len(set(words))
    type_token = (unique / len(words)) if words else 0.0
    title_words = tokenize(title or "")
    return {
        "log_chars": math.log1p(chars),
        "log_words": math.log1p(len(words)),
        "sentence_count": float(len(sentences)),
        "bullet_ratio": (bullets / max(len(lines), 1)),
        "avg_word_len": avg_word,
        "type_token": type_token,
        "title_len": float(len(title or "")),
        "title_word_count": float(len(title_words)),
        "has_question": 1.0 if "?" in text else 0.0,
        "has_action_verb": 1.0
        if re.search(r"\b(learn|practice|apply|identify|explain|demonstrate|avoid)\b", text, re.I)
        else 0.0,
        "short_page_penalty": 1.0 if chars < 80 else 0.0,
        "long_page_penalty": 1.0 if chars > 3500 else 0.0,
        "density": (len(words) / max(chars, 1)) * 100.0,
    }


def token_counts(title: str, body: str, max_tokens: int = 80) -> Counter[str]:
    counts: Counter[str] = Counter()
    for tok in tokenize(f"{title} {body}"):
        counts[tok] += 1
    # Keep head by frequency for compact models.
    return Counter(dict(counts.most_common(max_tokens)))
