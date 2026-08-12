"""Lab assignment models (richer than production aoep_shared.homework)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .methodologies import GradingMode, get_methodology


class MediaRef(BaseModel):
    kind: str = "none"  # image | video | audio | diagram | none
    uri: str = ""
    alt: str = ""
    transcript: str = ""
    duration_s: float = 0.0
    meta: Dict[str, Any] = Field(default_factory=dict)


class LabItem(BaseModel):
    item_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    methodology: str
    family: str = ""
    grading_mode: str = ""
    prompt: str
    topic: str = ""
    difficulty: str = "medium"
    options: List[str] = Field(default_factory=list)
    # Keying — shape depends on methodology (see grade.py).
    answer_key: Any = None
    rubric: List[str] = Field(default_factory=list)
    media: MediaRef = Field(default_factory=MediaRef)
    pairs: List[Dict[str, str]] = Field(default_factory=list)  # matching / memory
    blanks: List[str] = Field(default_factory=list)
    locale: str = "en"
    source_ref: str = ""  # verse line, slide id, etc.
    meta: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:  # pydantic v2
        try:
            m = get_methodology(self.methodology)
        except KeyError:
            return
        if not self.family:
            self.family = m.family
        if not self.grading_mode:
            self.grading_mode = m.grading_mode.value


class LabAssignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    subject: str = "general"
    source: str = ""
    locale: str = "en"
    items: List[LabItem] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @property
    def methodologies_used(self) -> List[str]:
        return sorted({it.methodology for it in self.items})


class ItemGrade(BaseModel):
    item_id: str
    methodology: str
    correct: Optional[bool] = None
    score: float = 0.0
    max_score: float = 1.0
    rationale: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class LabGradeReport(BaseModel):
    assignment_id: str
    score: float
    max_score: float
    percentage: float
    items: List[ItemGrade] = Field(default_factory=list)
    methodology_coverage: Dict[str, int] = Field(default_factory=dict)
    validity_flags: List[str] = Field(default_factory=list)
