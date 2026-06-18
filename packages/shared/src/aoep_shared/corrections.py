"""Standardized course/model corrections + back-propagation.

A single `Correction` model covers two back-prop targets: course content (patch a
deck/scene/lesson) and the training model (emit a gold training example). Single
and bulk (CSV/JSONL) entry are supported. `correction_to_training_example`
produces a high-reward gold example for the training pipeline, with the same
fairness guardrail used elsewhere: protected attributes (race, ethnicity) are
never written into the training context.
"""

from __future__ import annotations

import csv
import enum
import io
import json
import time
import uuid
from typing import Dict, List

from pydantic import BaseModel, Field

# Mirror of the training pipeline's guardrail (kept local so services don't
# need the training/ package on the import path).
CONDITIONING_FEATURES = (
    "age_band", "language", "reading_level", "learning_style",
    "professionalism", "prior_mastery",
)
PROTECTED_ATTRIBUTES = ("race", "ethnicity")


class TargetKind(str, enum.Enum):
    COURSE = "course"
    DECK = "deck"
    SCENE = "scene"
    CLAIM = "claim"
    MODEL = "model"


class CorrectionStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


class Correction(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    target_kind: TargetKind = TargetKind.COURSE
    target_id: str = ""
    locator: str = ""        # slide index, claim text, or the prompt for a model fix
    original: str = ""
    corrected: str = ""
    rationale: str = ""
    author: str = ""
    status: CorrectionStatus = CorrectionStatus.SUBMITTED
    audience: Dict[str, object] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())


_FIELDS = ("target_kind", "target_id", "locator", "original", "corrected",
           "rationale", "author")


def _from_row(row: Dict[str, object]) -> Correction:
    data = {k: row[k] for k in _FIELDS if k in row and row[k] not in (None, "")}
    if "audience" in row and row["audience"]:
        aud = row["audience"]
        data["audience"] = json.loads(aud) if isinstance(aud, str) else aud
    return Correction(**data)


def parse_bulk(text: str, fmt: str = "jsonl") -> List[Correction]:
    """Parse many corrections from a CSV or JSONL blob (bulk entry)."""
    fmt = fmt.lower()
    out: List[Correction] = []
    if fmt == "jsonl":
        for line in text.splitlines():
            line = line.strip()
            if line:
                out.append(_from_row(json.loads(line)))
    elif fmt == "csv":
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if any((v or "").strip() for v in row.values()):
                out.append(_from_row(row))
    else:
        raise ValueError(f"unsupported bulk format: {fmt!r} (use 'csv' or 'jsonl')")
    return out


def _conditioning_context(audience: Dict[str, object]) -> Dict[str, object]:
    """Allowlisted, non-protected audience features only."""
    return {k: audience[k] for k in CONDITIONING_FEATURES if k in audience}


def correction_to_training_example(correction: Correction) -> Dict[str, object]:
    """Convert a correction into a gold (reward=+1) training example.

    `locator` (or `original`) is treated as the prompt; `corrected` is the gold
    response. Protected attributes are excluded from the context by design.
    """
    instruction = (correction.locator or correction.original).strip()
    return {
        "instruction": instruction,
        "context": _conditioning_context(correction.audience),
        "response": correction.corrected.strip(),
        "reward": 1.0,
        "tags": ["correction", correction.target_kind.value],
    }
