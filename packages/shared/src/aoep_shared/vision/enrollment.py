"""Choose which face photos become a learner's templates.

The phone sends more clear photos than it needs. The first one used to be the
reference for all the others, so one blurred or tilted first frame could sink
the whole check. With extra photos we pick the most typical face as the
reference and keep the best five. With exactly five, every photo must match the
first, as before.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .engine import DEFAULT_MATCH_THRESHOLD, LIVENESS_TEMPLATE_COUNT, cosine_similarity


def _min_sharpness() -> float:
    try:
        return float(os.getenv("AOEP_FACE_MIN_SHARPNESS", "15"))
    except ValueError:
        return 15.0


@dataclass
class Candidate:
    index: int  # 1-based position in the request
    embedding: Sequence[float]
    det_score: float = 1.0
    sharpness: Optional[float] = None
    roll: Optional[float] = None


class EnrollmentRefused(Exception):
    """The photos cannot make a face check; ``detail`` is safe to show the learner."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def _quality(c: Candidate, similarity: float) -> float:
    sharp = 60.0 if c.sharpness is None else c.sharpness
    tilt = abs(c.roll) if c.roll is not None else 0.0
    return similarity + 0.5 * min(max(c.det_score, 0.0), 1.0) + 0.3 * min(sharp / 60.0, 1.0) - 0.004 * tilt


def choose_templates(
    candidates: Sequence[Candidate],
    *,
    keep: int = LIVENESS_TEMPLATE_COUNT,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> List[Candidate]:
    """The photos to store, reference first. Raises EnrollmentRefused when too few agree."""
    items = list(candidates)
    if len(items) <= keep:
        anchor = items[0]
        for item in items[1:]:
            score = cosine_similarity(anchor.embedding, item.embedding)
            if score < threshold:
                raise EnrollmentRefused(
                    f"photo {item.index} does not look like the same person ({score:.2f})"
                )
        return items

    floor = _min_sharpness()
    pool = [c for c in items if c.sharpness is None or c.sharpness >= floor]
    if len(pool) < keep:
        pool = items  # blur only decides when enough sharp photos remain

    def typical(c: Candidate) -> float:
        others = [cosine_similarity(c.embedding, o.embedding) for o in pool if o is not c]
        return sum(others) / len(others) if others else 0.0

    anchor = max(pool, key=lambda c: (typical(c), c.det_score))
    scored = [(c, 1.0 if c is anchor else cosine_similarity(anchor.embedding, c.embedding)) for c in pool]
    agreeing = [(c, sim) for c, sim in scored if sim >= threshold]
    if len(agreeing) < keep:
        raise EnrollmentRefused(
            f"only {len(agreeing)} of {len(items)} photos showed the same clear face. "
            "Look straight at the camera, hold still, and try again."
        )
    rest = sorted(
        ((c, sim) for c, sim in agreeing if c is not anchor),
        key=lambda pair: _quality(pair[0], pair[1]),
        reverse=True,
    )
    return [anchor] + [c for c, _ in rest[: keep - 1]]
