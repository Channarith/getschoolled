"""Offline quality metrics and publish tiers for harvested decks.

Tiers (what the catalog may say about a deck):
  0  machine-generated, unreviewed (always labelled as such)
  1  auto-validated: structure/text gate passed, composition score ok, not a near-duplicate,
     and (when a corroboration hook is supplied) its claims were corroborated
  2  human-reviewed (set only by the staff review flow, never by this module)

Near-duplicate detection uses MinHash over word shingles (stdlib only, deterministic) so
the 50-decks-per-source-page partitioning cannot flood the catalog with repeats.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence

TIER_MACHINE = 0
TIER_AUTO_VALIDATED = 1
TIER_HUMAN_REVIEWED = 2

_PLACEHOLDER = re.compile(r"lorem ipsum|\btodo\b|\bplaceholder\b|\bclick here\b|\[\s*insert", re.I)
_WORD = re.compile(r"\w+", re.UNICODE)

DEFAULT_GATE = {
    "min_slides": 6,
    "min_text_chars": 3000,
    "min_avg_slide_chars": 150,
    "max_placeholder_ratio": 0.02,
    "max_repeat_ratio": 0.30,
    "min_composition_score": 300,
}


def slide_texts(course: dict) -> List[str]:
    texts = []
    for slide in course.get("slides") or []:
        parts = [slide.get(k) for k in ("title", "body", "narration", "notes", "speaker_notes")]
        texts.append(" ".join(p for p in parts if isinstance(p, str)))
    return texts


def course_text(course: dict) -> str:
    return "\n".join(slide_texts(course))


def metrics(course: dict) -> Dict[str, float]:
    texts = slide_texts(course)
    total = sum(len(t) for t in texts)
    n = len(texts)
    placeholder = sum(1 for t in texts if _PLACEHOLDER.search(t))
    unique = len({re.sub(r"\W+", " ", t.lower()).strip() for t in texts if t.strip()})
    return {
        "slides": n,
        "text_chars": total,
        "avg_slide_chars": (total / n) if n else 0,
        "placeholder_ratio": (placeholder / n) if n else 1.0,
        "repeat_ratio": (1 - unique / n) if n else 1.0,
        "composition_score": float(course.get("composition_score") or 0),
    }


def gate_failures(m: Dict[str, float], gate: Optional[Dict[str, float]] = None) -> List[str]:
    g = {**DEFAULT_GATE, **(gate or {})}
    out = []
    if m["slides"] < g["min_slides"]:
        out.append(f"too few slides ({int(m['slides'])})")
    if m["text_chars"] < g["min_text_chars"]:
        out.append(f"too little text ({int(m['text_chars'])} chars)")
    if m["avg_slide_chars"] < g["min_avg_slide_chars"]:
        out.append("slides are too thin")
    if m["placeholder_ratio"] > g["max_placeholder_ratio"]:
        out.append("placeholder text present")
    if m["repeat_ratio"] > g["max_repeat_ratio"]:
        out.append("repeated slides")
    if m["composition_score"] < g["min_composition_score"]:
        out.append(f"low composition score ({int(m['composition_score'])})")
    return out


# --- MinHash near-duplicate detection ------------------------------------------- #


def _shingles(text: str, k: int = 5) -> set:
    words = _WORD.findall(text.lower())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def minhash(text: str, num_perm: int = 64) -> tuple:
    sh = _shingles(text)
    if not sh:
        return tuple([0] * num_perm)
    hashes = [
        int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")
        for s in sh
    ]
    sig = []
    for seed in range(num_perm):
        mask = (seed * 0x9E3779B97F4A7C15 + 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        sig.append(min((h ^ mask) * 0xFF51AFD7ED558CCD & 0xFFFFFFFFFFFFFFFF for h in hashes))
    return tuple(sig)


def similarity(a: Sequence[int], b: Sequence[int]) -> float:
    return sum(1 for x, y in zip(a, b) if x == y) / max(1, len(a))


class NearDuplicateIndex:
    """LSH-banded index: add() returns the id of an existing near-duplicate or None."""

    def __init__(self, threshold: float = 0.85, bands: int = 16, num_perm: int = 64) -> None:
        if num_perm % bands:
            raise ValueError("num_perm must be divisible by bands")
        self.threshold, self.bands, self.rows = threshold, bands, num_perm // bands
        self._buckets: Dict[tuple, List[str]] = {}
        self._sigs: Dict[str, tuple] = {}
        self._num_perm = num_perm

    def add(self, key: str, text: str) -> Optional[str]:
        sig = minhash(text, self._num_perm)
        for b in range(self.bands):
            band = (b, sig[b * self.rows : (b + 1) * self.rows])
            for other in self._buckets.get(band, []):
                if similarity(sig, self._sigs[other]) >= self.threshold:
                    return other
        for b in range(self.bands):
            self._buckets.setdefault((b, sig[b * self.rows : (b + 1) * self.rows]), []).append(key)
        self._sigs[key] = sig
        return None


@dataclass
class TierDecision:
    tier: int
    failures: List[str] = field(default_factory=list)
    duplicate_of: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


def assign_tier(
    course: dict,
    *,
    key: str,
    dedup: Optional[NearDuplicateIndex] = None,
    corroborate: Optional[Callable[[dict], bool]] = None,
    gate: Optional[Dict[str, float]] = None,
) -> TierDecision:
    """Tier 0 unless every automatic gate passes. Never returns tier 2."""
    m = metrics(course)
    failures = gate_failures(m, gate)
    dup = dedup.add(key, course_text(course)) if dedup is not None else None
    if dup:
        failures.append(f"near-duplicate of {dup}")
    if not failures and corroborate is not None and not corroborate(course):
        failures.append("claims not corroborated")
    return TierDecision(TIER_MACHINE if failures else TIER_AUTO_VALIDATED, failures, dup, m)


def sample_for_review(
    ids_by_source: Dict[str, Iterable[str]], fraction: float = 0.01, minimum: int = 1
) -> Dict[str, List[str]]:
    """Deterministic 1%-per-source QA sample (at least `minimum` per source), by sha order."""
    picked: Dict[str, List[str]] = {}
    for source, ids in ids_by_source.items():
        ordered = sorted(ids, key=lambda i: hashlib.sha256(f"{source}|{i}".encode()).hexdigest())
        n = max(minimum, int(len(ordered) * fraction)) if ordered else 0
        picked[source] = ordered[:n]
    return picked
