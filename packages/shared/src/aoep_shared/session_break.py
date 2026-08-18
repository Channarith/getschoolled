"""Session break / segmentation logic for long lessons.

Long lessons (>= BREAK_MIN_SLIDES slides) are silently divided into segments.
After each segment boundary the advance response includes a ``segment_break``
field so clients can offer the learner "Take a break or keep going?".

Segment sizes (in slides) are derived from the lesson length and a requested
granularity:
  - SHORT  segment ≈ 10 min → roughly 8 slides at the teaching rate
  - MEDIUM segment ≈ 15 min → roughly 12 slides
  - LONG   segment ≈ 20 min → roughly 16 slides

The caller (orchestrator advance endpoint) decides the granularity based on the
lesson's total slide count (short lessons ≤ 24 slides → 20-min segments; longer
lessons fall into 15 or 10-min segments so breaks stay frequent).

Break windows are ``segment_size × n``, not measured wall-clock time (clients
control actual narration speed) — the server just marks boundary slides.
"""

from __future__ import annotations

import math
from typing import Any

# Minimum slides before we insert any breaks at all.
BREAK_MIN_SLIDES = 15

# Rough slides-per-minute estimate at the instructional narration rate
# (DEFAULT_SLIDE_MINUTES ≈ 1.25 min/slide from lesson_depth.py).
SLIDES_PER_MINUTE = 0.8  # conservative: ~1.25 min/slide

# The three granularity tiers expressed as target-minutes.
SEGMENT_MINUTES_SHORT = 10
SEGMENT_MINUTES_MEDIUM = 15
SEGMENT_MINUTES_LONG = 20


def _segment_size(total_slides: int) -> int:
    """How many slides make one segment based on lesson length."""
    if total_slides <= 24:
        target = SEGMENT_MINUTES_LONG
    elif total_slides <= 40:
        target = SEGMENT_MINUTES_MEDIUM
    else:
        target = SEGMENT_MINUTES_SHORT
    size = max(6, round(target * SLIDES_PER_MINUTE))
    # Avoid a tiny stub at the end: if the last segment would be < 40% of a
    # full segment, roll those slides into the penultimate segment.
    last_seg_size = total_slides % size
    if last_seg_size > 0 and last_seg_size < max(3, int(size * 0.4)):
        # Merge into previous by expanding the effective size slightly.
        size = max(size, math.ceil(total_slides / max(1, total_slides // size)))
    return size


def break_slide_indices(total_slides: int) -> frozenset[int]:
    """Return the set of 0-based slide indices after which a break is offered.

    The *last* slide is never a break boundary (the lesson finishes there).
    """
    if total_slides < BREAK_MIN_SLIDES:
        return frozenset()
    size = _segment_size(total_slides)
    boundaries: list[int] = []
    idx = size - 1  # index *after* which the break fires
    while idx < total_slides - 1:
        boundaries.append(idx)
        idx += size
    return frozenset(boundaries)


def segment_break_payload(
    slide_index: int,
    total_slides: int,
    *,
    segment_size: int | None = None,
    elapsed_slides: int | None = None,
) -> dict[str, Any] | None:
    """Return the break payload if ``slide_index`` is a break boundary, else None.

    ``elapsed_slides`` — how many slides the learner has seen this session.
    """
    size = segment_size if segment_size is not None else _segment_size(total_slides)
    boundaries = break_slide_indices(total_slides)
    if slide_index not in boundaries:
        return None
    segment_num = (slide_index + 1) // size
    remaining = total_slides - slide_index - 1
    mins_done = round((slide_index + 1) / SLIDES_PER_MINUTE)
    mins_left = round(remaining / SLIDES_PER_MINUTE)
    return {
        "due": True,
        "segment": segment_num,
        "slide_index": slide_index,
        "slides_done": slide_index + 1,
        "slides_remaining": remaining,
        "approx_minutes_done": mins_done,
        "approx_minutes_remaining": mins_left,
        "message": (
            f"You've finished segment {segment_num} — about {mins_done} minutes in. "
            f"There's roughly {mins_left} more minutes left. "
            "Take a break and come back later, or keep going right now."
        ),
        "choices": [
            {"id": "continue", "label": "Keep going"},
            {"id": "break", "label": "Take a break"},
        ],
    }
