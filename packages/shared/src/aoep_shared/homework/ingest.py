"""Homework submission ingest (Phase 7).

Normalizes OCR output (typed or handwritten) into a Submission, with a simple
per-question segmentation so the autograder (Phase 9) can score answer-by-answer.
"""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field

from ..providers.base import OcrResult

# Split on "1." / "2)" / "Q3:" style answer markers.
_MARKER = re.compile(r"(?:^|\n)\s*(?:q?\s*\d+\s*[\.\):])", re.IGNORECASE)


class Submission(BaseModel):
    raw_text: str
    handwritten: bool = False
    confidence: float = 1.0
    segments: List[str] = Field(default_factory=list)


def segment_answers(text: str, *, expected: Optional[int] = None) -> List[str]:
    """Split a free-text submission into per-question answers."""
    text = text.strip()
    if not text:
        return []
    parts = [p.strip() for p in _MARKER.split(text) if p.strip()]
    if len(parts) <= 1:
        # No numbered markers: fall back to blank-line separated blocks.
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()] or [text]
    return parts


def ocr_to_submission(result: OcrResult, *, expected: Optional[int] = None) -> Submission:
    return Submission(
        raw_text=result.text,
        handwritten=result.handwritten,
        confidence=result.confidence,
        segments=segment_answers(result.text, expected=expected),
    )
