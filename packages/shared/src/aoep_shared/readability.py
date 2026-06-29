"""Language complexity & readability — scoring and on-the-fly simplification.

Greenfield capability that quantifies how hard text is to read and can simplify
it toward a target reading level so the Tutor/Presenter can match a learner's
language complexity. Pure/stdlib-only and deterministic.

Metrics:
- Flesch Reading Ease (higher = easier).
- Flesch-Kincaid Grade level.
- A CEFR estimate (A1-C2) for second-language learners.
- A coarse reading-level bucket (beginner | intermediate | advanced) consistent
  with the existing learner-profile vocabulary.

The simplifier is a deterministic heuristic (sentence-splitting + a complex->
simple word map). It is intentionally lightweight; an LLM polish layer can sit
behind the same ``simplify_text`` signature. The word map is extensible via
content packs of kind ``readability`` (records: {"complex": ..., "simple": ...}).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List

_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_SENT_RE = re.compile(r"[.!?]+")


def count_syllables(word: str) -> int:
    w = word.lower().strip()
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ye")) and n > 1:
        n -= 1
    return max(1, n)


def _counts(text: str) -> tuple[int, int, int]:
    words = _WORD_RE.findall(text or "")
    n_words = len(words)
    sentences = [s for s in _SENT_RE.split(text or "") if s.strip()]
    n_sentences = max(1, len(sentences))
    n_syllables = sum(count_syllables(w) for w in words)
    return n_words, n_sentences, n_syllables


def flesch_reading_ease(text: str) -> float:
    w, s, syl = _counts(text)
    if w == 0:
        return 0.0
    score = 206.835 - 1.015 * (w / s) - 84.6 * (syl / w)
    return round(max(-50.0, min(120.0, score)), 1)


def flesch_kincaid_grade(text: str) -> float:
    w, s, syl = _counts(text)
    if w == 0:
        return 0.0
    grade = 0.39 * (w / s) + 11.8 * (syl / w) - 15.59
    return round(max(0.0, grade), 1)


def cefr_estimate(text: str) -> str:
    """Approximate CEFR level from reading ease (A1 easiest, C2 hardest)."""
    ease = flesch_reading_ease(text)
    if ease >= 90:
        return "A1"
    if ease >= 80:
        return "A2"
    if ease >= 65:
        return "B1"
    if ease >= 50:
        return "B2"
    if ease >= 30:
        return "C1"
    return "C2"


def reading_level(text: str) -> str:
    """Coarse bucket aligned with the learner-profile vocabulary."""
    grade = flesch_kincaid_grade(text)
    if grade <= 6:
        return "beginner"
    if grade <= 11:
        return "intermediate"
    return "advanced"


@dataclass
class ReadabilityReport:
    words: int
    sentences: int
    syllables: int
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    cefr: str
    reading_level: str

    def to_dict(self) -> dict:
        return {
            "words": self.words,
            "sentences": self.sentences,
            "syllables": self.syllables,
            "flesch_reading_ease": self.flesch_reading_ease,
            "flesch_kincaid_grade": self.flesch_kincaid_grade,
            "cefr": self.cefr,
            "reading_level": self.reading_level,
        }


def analyze(text: str) -> ReadabilityReport:
    w, s, syl = _counts(text)
    return ReadabilityReport(
        words=w,
        sentences=s,
        syllables=syl,
        flesch_reading_ease=flesch_reading_ease(text),
        flesch_kincaid_grade=flesch_kincaid_grade(text),
        cefr=cefr_estimate(text),
        reading_level=reading_level(text),
    )


# --------------------------------------------------------------------------- #
# Simplification
# --------------------------------------------------------------------------- #
_BUILTIN_SIMPLE_MAP: Dict[str, str] = {
    "utilize": "use", "utilise": "use", "commence": "start", "terminate": "end",
    "purchase": "buy", "obtain": "get", "require": "need", "demonstrate": "show",
    "facilitate": "help", "assist": "help", "approximately": "about",
    "subsequently": "later", "additionally": "also", "however": "but",
    "therefore": "so", "consequently": "so", "numerous": "many",
    "sufficient": "enough", "endeavor": "try", "endeavour": "try",
    "comprehend": "understand", "ascertain": "find out", "initiate": "start",
    "prioritize": "rank", "prioritise": "rank", "fundamental": "basic",
    "approximately": "about", "accommodate": "fit", "anticipate": "expect",
    "component": "part", "objective": "goal", "regarding": "about",
    "previously": "before", "currently": "now", "immediately": "right away",
    "assistance": "help", "individual": "person", "maintain": "keep",
    "modify": "change", "construct": "build", "eliminate": "remove",
    "indicate": "show", "sufficient": "enough", "frequently": "often",
    "approximately": "about", "in order to": "to", "due to the fact that": "because",
    "a large number of": "many", "at this point in time": "now",
    "in the event that": "if", "with regard to": "about",
}

_MAX_SENTENCE_WORDS = {
    "beginner": 12,
    "intermediate": 20,
    "advanced": 100,
}


@lru_cache(maxsize=1)
def _pack_fingerprint_cached() -> str:
    try:
        from .content_packs import pack_fingerprint

        return pack_fingerprint("readability")
    except Exception:  # pragma: no cover
        return ""


_simple_map_cache: dict = {"fingerprint": None, "map": None}


def _simple_map() -> Dict[str, str]:
    try:
        from .content_packs import load_records, pack_fingerprint

        fp = pack_fingerprint("readability")
    except Exception:  # pragma: no cover
        return dict(_BUILTIN_SIMPLE_MAP)
    if _simple_map_cache["fingerprint"] == fp and _simple_map_cache["map"] is not None:
        return _simple_map_cache["map"]
    merged = dict(_BUILTIN_SIMPLE_MAP)
    for rec in load_records("readability"):
        complex_w = rec.get("complex")
        simple_w = rec.get("simple")
        if complex_w and simple_w:
            merged[str(complex_w).lower()] = str(simple_w)
    _simple_map_cache["fingerprint"] = fp
    _simple_map_cache["map"] = merged
    return merged


def _apply_word_map(text: str, mapping: Dict[str, str]) -> str:
    # Multi-word phrases first (longest), then single words.
    phrases = sorted((k for k in mapping if " " in k), key=len, reverse=True)
    for phrase in phrases:
        text = re.sub(re.escape(phrase), mapping[phrase], text, flags=re.IGNORECASE)

    def _repl(m: re.Match) -> str:
        word = m.group(0)
        repl = mapping.get(word.lower())
        if repl is None:
            return word
        if word[:1].isupper():
            return repl[:1].upper() + repl[1:]
        return repl

    return _WORD_RE.sub(_repl, text)


def _split_long_sentence(sentence: str, max_words: int) -> str:
    words = sentence.split()
    if len(words) <= max_words:
        return sentence
    # Split at coordinating conjunctions / discourse markers near the middle.
    connectors = {"and", "but", "or", "so", "because", "which", "while", "although"}
    best = None
    for i, tok in enumerate(words):
        if tok.lower().strip(",;") in connectors and max_words // 2 <= i <= len(words) - 3:
            best = i
            break
    if best is None:
        best = len(words) // 2
    left = " ".join(words[:best]).rstrip(",;")
    right = " ".join(words[best:]).lstrip()
    right = re.sub(r"^(and|but|or|so|because|which|while|although)\b[,]?\s*", "", right,
                   flags=re.IGNORECASE)
    if right:
        right = right[:1].upper() + right[1:]
    return f"{left}. {right}"


def simplify_text(text: str, *, reading_level: str = "beginner") -> str:
    """Heuristically simplify ``text`` toward a target reading level."""
    if not text:
        return text
    level = (reading_level or "beginner").lower()
    if level == "advanced":
        return text
    mapping = _simple_map()
    result = _apply_word_map(text, mapping)
    max_words = _MAX_SENTENCE_WORDS.get(level, 20)
    parts = re.split(r"(?<=[.!?])\s+", result)
    rebuilt = [_split_long_sentence(p, max_words) for p in parts if p.strip()]
    return " ".join(rebuilt).strip()


def grade_at_or_below(text: str, max_grade: float) -> bool:
    return flesch_kincaid_grade(text) <= max_grade
