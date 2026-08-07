"""Shared types for the course studio experiment."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QualityLabel(str, Enum):
    GOOD = "good"
    BETTER = "better"
    MODERATE = "moderate"
    BAD = "bad"
    UNLABELED = "unlabeled"


class PageVerdict(str, Enum):
    LIKE = "like"  # unmarked / keep
    DISLIKE = "dislike"  # circle + line-through style reject
    UNREVIEWED = "unreviewed"


class CategoryId(str, Enum):
    COMMUNICATION = "communication"
    LEADERSHIP = "leadership"
    SEXUAL_HARASSMENT = "sexual_harassment"
    OTHER = "other"


class SourceDocument(BaseModel):
    source_id: str
    category: CategoryId
    category_folder: str
    filename: str
    path: str
    ext: str  # pdf | pptx
    quality_label: QualityLabel = QualityLabel.UNLABELED
    title_guess: str = ""
    page_count: int | None = None
    incorporate: bool = False  # True when good/better (filename) unless overridden
    notes: str = ""


class PageReview(BaseModel):
    source_id: str
    page_index: int = Field(ge=0)  # 0-based
    verdict: PageVerdict = PageVerdict.UNREVIEWED
    # Manual circle+strikethrough equivalent from human review UI.
    marked_reject: bool = False
    comment: str = ""
    updated_at_ms: int = 0


class ReviewComment(BaseModel):
    comment_id: str
    source_id: str
    page_index: int | None = None
    course_id: str | None = None
    slide_index: int | None = None
    author: str = "reviewer"
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    created_at_ms: int = 0


class CourseSlide(BaseModel):
    index: int = Field(ge=0)
    title: str
    body: str
    narration: str = ""
    source_page: int | None = None
    keep: bool = True
    tags: list[str] = Field(default_factory=list)


class StudioCourse(BaseModel):
    course_id: str
    title: str
    category: CategoryId
    language: str = "en"  # aoep_shared SUPPORTED_LANGUAGES code
    source_ids: list[str] = Field(default_factory=list)
    slides: list[CourseSlide] = Field(default_factory=list)
    profile_adaptations: dict[str, Any] = Field(default_factory=dict)
    created_at_ms: int = 0
    status: str = "draft"  # draft | ready | teaching


class LearnerProfileScores(BaseModel):
    """Ecosystem user-profile scoring knobs that reshape Theodore's delivery."""

    engagement: float = Field(default=0.7, ge=0.0, le=1.0)
    literacy: float = Field(default=0.6, ge=0.0, le=1.0)
    attention: float = Field(default=0.7, ge=0.0, le=1.0)
    fatigue: float = Field(default=0.2, ge=0.0, le=1.0)
    confusion: float = Field(default=0.2, ge=0.0, le=1.0)
    pace_preference: float = Field(default=0.5, ge=0.0, le=1.0)  # 0 slow .. 1 fast
    accessibility_need: float = Field(default=0.3, ge=0.0, le=1.0)


class TeachTurn(BaseModel):
    slide_index: int
    title: str
    display_body: str
    narration: str
    adaptations_applied: list[str] = Field(default_factory=list)
    profile_snapshot: LearnerProfileScores | None = None


class TrainingRunReport(BaseModel):
    run_id: str
    corpus_root: str
    started_at_ms: int
    finished_at_ms: int = 0
    documents_scanned: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    incorporate_ids: list[str] = Field(default_factory=list)
    reject_ids: list[str] = Field(default_factory=list)
    review_queue_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
