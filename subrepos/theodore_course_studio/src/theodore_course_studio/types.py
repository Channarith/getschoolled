"""Shared types for the course studio experiment."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

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
    DRIVER_EDUCATION = "driver_education"
    FOOD_SAFETY = "food_safety"
    OTHER = "other"


AvatarGesture = Literal[
    "idle",
    "explain",
    "open-palm",
    "point-to-slide",
    "point-left",
    "point-right",
    "count",
    "compare",
    "caution",
    "stop",
    "demonstrate",
    "steer",
    "shoulder-check",
    "seatbelt",
    "phone-away",
    "wash-hands",
    "gloves",
    "thermometer",
    "sanitize",
    "ask",
    "listen",
    "celebrate",
    "transition",
]
AvatarGaze = Literal["learner", "slide", "left", "right", "down", "neutral"]
AvatarExpression = Literal[
    "neutral", "warm", "serious", "concerned", "curious", "encouraging", "celebrating"
]


class AvatarViseme(BaseModel):
    """A deterministic mouth target derived from narration text."""

    at_s: float = Field(ge=0)
    shape: Literal["rest", "aa", "ee", "oh", "fv", "mbp", "l", "wq"]
    weight: float = Field(default=0.8, ge=0, le=1)


class AvatarCue(BaseModel):
    """One blended body/facial action on the narration timeline."""

    start_s: float = Field(ge=0)
    duration_s: float = Field(default=1.5, gt=0, le=30)
    gesture: AvatarGesture = "explain"
    gaze: AvatarGaze = "learner"
    hand: Literal["left", "right", "both", "none"] = "none"
    intensity: float = Field(default=0.75, ge=0, le=1.5)
    expression: AvatarExpression = "warm"
    target: str = ""


class AvatarScript(BaseModel):
    """Complete offline choreography for one course slide."""

    version: int = 1
    state: Literal[
        "idle", "presenting", "speaking", "listening", "thinking", "celebrate", "paused"
    ] = "presenting"
    duration_s: float = Field(default=1, gt=0, le=600)
    cues: list[AvatarCue] = Field(default_factory=list)
    visemes: list[AvatarViseme] = Field(default_factory=list)
    source: Literal["curated", "inferred", "explicit"] = "inferred"


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
    # Stable id that survives title translation (e.g. ca-dmv-basics.following-distance).
    # Avatar cues and multimodal kits look this up first; English title is the fallback.
    slide_key: str = ""
    title: str
    body: str
    narration: str = ""
    picture_url: str = ""
    picture_alt: str = ""
    video_url: str = ""
    video_caption: str = ""
    # Inline SVG storyboard (CSS keyframes animate when injected as HTML, not <img>).
    storyboard_svg: str = ""
    storyboard_concept: str = ""
    storyboard_scene_id: str = ""
    activity_prompt: str = ""
    examples: list[str] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    quiz_spec: dict[str, Any] = Field(default_factory=dict)
    game_spec: dict[str, Any] = Field(default_factory=dict)
    source_page: int | None = None
    keep: bool = True
    tags: list[str] = Field(default_factory=list)
    avatar_script: AvatarScript | None = None


class StudioCourse(BaseModel):
    course_id: str
    title: str
    category: CategoryId
    language: str = "en"  # aoep_shared SUPPORTED_LANGUAGES code
    audience: str = "general"  # general | pre_k | kindergarten | grade_1 | grade_2
    subject: str = ""
    estimated_minutes: int = 18
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
    # How the learner prefers to take in each segment (all available; ranking guides UI).
    learn_from_images: float = Field(default=0.7, ge=0.0, le=1.0)
    learn_from_text: float = Field(default=0.7, ge=0.0, le=1.0)
    learn_from_video: float = Field(default=0.7, ge=0.0, le=1.0)
    learn_from_examples: float = Field(default=0.75, ge=0.0, le=1.0)
    learn_from_quiz: float = Field(default=0.55, ge=0.0, le=1.0)
    learn_from_games: float = Field(default=0.55, ge=0.0, le=1.0)
    learn_from_activity: float = Field(default=0.5, ge=0.0, le=1.0)


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
