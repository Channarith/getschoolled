"""AI-vs-human authorship detection (Phase 8).

A transparent, offline heuristic detector. It scores how "machine-uniform" a
submission reads (low sentence-length burstiness + high lexical regularity are
AI-leaning) and folds in a handwriting signal (handwritten work is a strong
human indicator). Returns a probability + the contributing signals.

IMPORTANT: detectors are probabilistic, NOT proof. A student can retype AI
output, and handwriting only proves a human formed the strokes, not that they
authored the content. Treat the verdict as a SIGNAL that routes borderline cases
to the human-in-the-loop review (Phase 10-12), never as an automatic penalty. A
real model-based detector can be swapped in behind this same interface.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Dict

_SENT = re.compile(r"[.!?]+")
_WORD = re.compile(r"[a-zA-Z0-9']+")


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class AuthorshipVerdict:
    label: str            # "human" | "ai" | "uncertain"
    ai_probability: float
    signals: Dict[str, float] = field(default_factory=dict)


def detect_authorship(text: str, *, handwritten: bool = False) -> AuthorshipVerdict:
    sentences = [s.strip() for s in _SENT.split(text) if s.strip()]
    lengths = [len(_WORD.findall(s)) for s in sentences]
    lengths = [n for n in lengths if n > 0]

    signals: Dict[str, float] = {"sentence_count": float(len(lengths))}

    if len(lengths) < 2:
        # Too little signal to judge from text alone.
        ai_prob = 0.2 if handwritten else 0.5
        signals["handwritten"] = float(handwritten)
        label = "human" if ai_prob <= 0.4 else "uncertain"
        return AuthorshipVerdict(label=label, ai_probability=round(ai_prob, 3), signals=signals)

    mean_len = statistics.mean(lengths)
    stdev_len = statistics.pstdev(lengths)
    cv = (stdev_len / mean_len) if mean_len else 0.0
    # Uniform sentence lengths (low coefficient of variation) read machine-like.
    burstiness_signal = _clamp(1.0 - cv / 0.5)

    words = _WORD.findall(text.lower())
    ttr = (len(set(words)) / len(words)) if words else 0.0

    ai_prob = burstiness_signal
    if handwritten:
        # Strong human prior: scanned handwriting is unlikely to be AI-authored.
        ai_prob *= 0.4

    signals.update({
        "cv": round(cv, 3),
        "burstiness_signal": round(burstiness_signal, 3),
        "type_token_ratio": round(ttr, 3),
        "mean_sentence_len": round(mean_len, 2),
        "handwritten": float(handwritten),
    })

    if ai_prob >= 0.6:
        label = "ai"
    elif ai_prob <= 0.4:
        label = "human"
    else:
        label = "uncertain"
    return AuthorshipVerdict(label=label, ai_probability=round(ai_prob, 3), signals=signals)
