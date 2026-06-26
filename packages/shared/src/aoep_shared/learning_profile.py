"""One-time onboarding learning-behavior survey + learner categorization.

Captures how someone learns best (modalities, pace, structure, accessibility
needs) so courses can be adapted and learners grouped into teaching categories.
Pure/offline; identity persists the profile on the student record and memory
stores anonymized rollups for analytics.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, Field

from .survey import SurveyQuestion

ONBOARDING_SURVEY_VERSION = "1.0"

# Comprehensive one-time gauge shown after signup (kept focused for completion).
ONBOARDING_LEARNING_SURVEY: List[SurveyQuestion] = [
    SurveyQuestion(
        "primary_style",
        "choice",
        "When learning something new, what helps you most?",
        options=(
            "Visual — diagrams, video, demonstrations",
            "Auditory — listening, discussion, narration",
            "Reading & writing — notes, text, written steps",
            "Hands-on — practice, labs, doing it yourself",
            "Mixed — no single style stands out",
        ),
        required=True,
    ),
    SurveyQuestion(
        "pace",
        "choice",
        "What pace feels best when material is new to you?",
        options=("Slower with more review", "Moderate and steady", "Faster with less repetition"),
        required=True,
    ),
    SurveyQuestion(
        "structure",
        "choice",
        "How do you prefer lessons to be organized?",
        options=(
            "Step-by-step in order",
            "Examples first, then rules",
            "Big picture first, then details",
            "Short bursts with frequent practice",
        ),
        required=True,
    ),
    SurveyQuestion(
        "session_length",
        "choice",
        "Ideal study session length for you:",
        options=("About 10 minutes", "About 20–30 minutes", "45 minutes or longer"),
        required=True,
    ),
    SurveyQuestion(
        "group_preference",
        "choice",
        "Do you learn better alone or with others?",
        options=("Mostly on my own", "Small group or class", "Either works for me"),
        required=True,
    ),
    SurveyQuestion(
        "reading_level",
        "choice",
        "Comfort level with reading-heavy material:",
        options=("Beginner — keep language simple", "Intermediate", "Advanced — dense text is fine"),
        required=True,
    ),
    SurveyQuestion(
        "motivation",
        "choice",
        "What brings you here today? (helps us suggest courses)",
        options=("Career / job skills", "School or certification", "Personal curiosity", "Other"),
        required=True,
    ),
    SurveyQuestion(
        "needs_captions",
        "bool",
        "I benefit from captions or transcripts for audio/video",
    ),
    SurveyQuestion(
        "needs_large_text",
        "bool",
        "I benefit from larger text or high-contrast display",
    ),
    SurveyQuestion(
        "needs_extra_time",
        "bool",
        "I benefit from extra time on quizzes and assessments",
    ),
    SurveyQuestion(
        "uses_assistive_tech",
        "bool",
        "I use assistive technology (screen reader, voice control, etc.)",
    ),
    SurveyQuestion(
        "accommodations_notes",
        "text",
        "Anything else we should know to support your learning? (optional)",
    ),
]

_STYLE_KEY = {
    "Visual — diagrams, video, demonstrations": "visual",
    "Auditory — listening, discussion, narration": "auditory",
    "Reading & writing — notes, text, written steps": "reading_writing",
    "Hands-on — practice, labs, doing it yourself": "hands_on",
    "Mixed — no single style stands out": "mixed",
}

_PACE_KEY = {
    "Slower with more review": "slow",
    "Moderate and steady": "moderate",
    "Faster with less repetition": "fast",
}

_STRUCTURE_KEY = {
    "Step-by-step in order": "step_by_step",
    "Examples first, then rules": "examples_first",
    "Big picture first, then details": "big_picture",
    "Short bursts with frequent practice": "practice_heavy",
}

_SESSION_KEY = {
    "About 10 minutes": "short",
    "About 20–30 minutes": "medium",
    "45 minutes or longer": "long",
}

_GROUP_KEY = {
    "Mostly on my own": "solo",
    "Small group or class": "group",
    "Either works for me": "either",
}

_READING_KEY = {
    "Beginner — keep language simple": "beginner",
    "Intermediate": "intermediate",
    "Advanced — dense text is fine": "advanced",
}

_MOTIVATION_KEY = {
    "Career / job skills": "career",
    "School or certification": "school",
    "Personal curiosity": "personal",
    "Other": "other",
}

# Teaching cohort buckets used for grouping + adaptive cold-start.
LEARNER_CATEGORIES: Tuple[str, ...] = (
    "visual_step_by_step",
    "visual_exploratory",
    "auditory_collaborative",
    "reading_structured",
    "hands_on_practice",
    "mixed_balanced",
    "accessibility_supported",
    "slow_paced_learner",
    "fast_paced_learner",
)


class LearningProfile(BaseModel):
    """Declarative learning preferences derived from the onboarding survey."""

    primary_style: str = "mixed"
    pace: str = "moderate"
    structure: str = "step_by_step"
    session_length: str = "medium"
    group_preference: str = "either"
    reading_level: str = "intermediate"
    motivation: str = "personal"
    accessibility: Dict[str, bool] = Field(default_factory=dict)
    accommodations_notes: str = ""
    learner_category: str = "mixed_balanced"
    raw_answers: Dict[str, Any] = Field(default_factory=dict)
    completed_at: float = Field(default_factory=lambda: time.time())


class OnboardingSurveyRecord(BaseModel):
    """Analytics record (memory service)."""

    id: str = Field(default_factory=lambda: f"ob-{int(time.time()*1000)}")
    account_id: str = ""
    student_id: str = ""
    profile: LearningProfile
    created_at: float = Field(default_factory=lambda: time.time())


def onboarding_template() -> Dict:
    return {
        "version": ONBOARDING_SURVEY_VERSION,
        "title": "How do you learn best?",
        "subtitle": (
            "One-time setup so we can adapt courses to your style. "
            "Accessibility answers are optional but help us support you."
        ),
        "questions": [
            {
                "id": q.id,
                "type": q.type,
                "prompt": q.prompt,
                "options": list(q.options),
                "required": q.required,
            }
            for q in ONBOARDING_LEARNING_SURVEY
        ],
        "categories": list(LEARNER_CATEGORIES),
    }


def _norm_choice(raw: Any, mapping: Dict[str, str], default: str) -> str:
    if raw is None:
        return default
    s = str(raw).strip()
    return mapping.get(s, default)


def derive_learning_profile(answers: Dict[str, Any]) -> LearningProfile:
    """Map survey answers to a structured profile + teaching category."""
    primary = _norm_choice(answers.get("primary_style"), _STYLE_KEY, "mixed")
    pace = _norm_choice(answers.get("pace"), _PACE_KEY, "moderate")
    structure = _norm_choice(answers.get("structure"), _STRUCTURE_KEY, "step_by_step")
    session_length = _norm_choice(answers.get("session_length"), _SESSION_KEY, "medium")
    group_preference = _norm_choice(answers.get("group_preference"), _GROUP_KEY, "either")
    reading_level = _norm_choice(answers.get("reading_level"), _READING_KEY, "intermediate")
    motivation = _norm_choice(answers.get("motivation"), _MOTIVATION_KEY, "personal")

    accessibility = {
        "needs_captions": bool(answers.get("needs_captions")),
        "needs_large_text": bool(answers.get("needs_large_text")),
        "needs_extra_time": bool(answers.get("needs_extra_time")),
        "uses_assistive_tech": bool(answers.get("uses_assistive_tech")),
    }
    notes = str(answers.get("accommodations_notes") or "").strip()

    category = categorize_learner(
        primary_style=primary,
        pace=pace,
        structure=structure,
        group_preference=group_preference,
        accessibility=accessibility,
    )

    return LearningProfile(
        primary_style=primary,
        pace=pace,
        structure=structure,
        session_length=session_length,
        group_preference=group_preference,
        reading_level=reading_level,
        motivation=motivation,
        accessibility=accessibility,
        accommodations_notes=notes,
        learner_category=category,
        raw_answers=dict(answers),
    )


def categorize_learner(
    *,
    primary_style: str,
    pace: str,
    structure: str,
    group_preference: str,
    accessibility: Dict[str, bool],
) -> str:
    """Assign a cohort bucket for course grouping and adaptive cold-start."""
    if any(accessibility.values()):
        return "accessibility_supported"
    if pace == "slow":
        return "slow_paced_learner"
    if pace == "fast":
        return "fast_paced_learner"

    if primary_style == "visual":
        return "visual_exploratory" if structure == "big_picture" else "visual_step_by_step"
    if primary_style == "auditory":
        return "auditory_collaborative" if group_preference != "solo" else "mixed_balanced"
    if primary_style == "reading_writing":
        return "reading_structured"
    if primary_style == "hands_on":
        return "hands_on_practice"
    return "mixed_balanced"


def validate_onboarding_answers(answers: Dict[str, Any]) -> None:
    """Raise ValueError when required questions are missing."""
    missing = []
    for q in ONBOARDING_LEARNING_SURVEY:
        if not q.required:
            continue
        val = answers.get(q.id)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(q.id)
    if missing:
        raise ValueError(f"missing required answers: {', '.join(missing)}")


def _invert_choice_map(mapping: Dict[str, str]) -> Dict[str, str]:
    return {v: k for k, v in mapping.items()}


def survey_answers_from_profile_fields(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuild survey form values from persisted student profile fields."""
    stored = profile.get("onboarding_answers") or {}
    if stored:
        return dict(stored)

    style = _invert_choice_map(_STYLE_KEY).get(profile.get("primary_style", ""), "")
    pace = _invert_choice_map(_PACE_KEY).get(profile.get("learning_pace", ""), "")
    structure = _invert_choice_map(_STRUCTURE_KEY).get(profile.get("learning_structure", ""), "")
    session = _invert_choice_map(_SESSION_KEY).get(profile.get("session_length", ""), "")
    group = _invert_choice_map(_GROUP_KEY).get(profile.get("group_preference", ""), "")
    reading = _invert_choice_map(_READING_KEY).get(profile.get("reading_level", ""), "")
    motivation = _invert_choice_map(_MOTIVATION_KEY).get(profile.get("motivation", ""), "")
    acc = profile.get("accessibility") or {}
    return {
        "primary_style": style,
        "pace": pace,
        "structure": structure,
        "session_length": session,
        "group_preference": group,
        "reading_level": reading,
        "motivation": motivation,
        "needs_captions": bool(acc.get("needs_captions")),
        "needs_large_text": bool(acc.get("needs_large_text")),
        "needs_extra_time": bool(acc.get("needs_extra_time")),
        "uses_assistive_tech": bool(acc.get("uses_assistive_tech")),
        "accommodations_notes": profile.get("accommodations_notes") or "",
    }


class OnboardingSurveyStore:
    """Analytics store for onboarding completions."""

    def __init__(self) -> None:
        self._records: List[OnboardingSurveyRecord] = []

    def submit(self, record: OnboardingSurveyRecord) -> OnboardingSurveyRecord:
        self._records.append(record)
        return record

    def count(self) -> int:
        return len(self._records)

    def summary(self) -> Dict:
        by_category: Dict[str, int] = {}
        by_style: Dict[str, int] = {}
        accessibility_count = 0
        for r in self._records:
            p = r.profile
            by_category[p.learner_category] = by_category.get(p.learner_category, 0) + 1
            by_style[p.primary_style] = by_style.get(p.primary_style, 0) + 1
            if any(p.accessibility.values()):
                accessibility_count += 1
        return {
            "responses": len(self._records),
            "by_category": by_category,
            "by_primary_style": by_style,
            "accessibility_supported_count": accessibility_count,
        }
