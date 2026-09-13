"""Compose behavioral segments into a full trial course."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .assessment import build_pop_quiz_for_slide
from .engagement import build_match_term_game, media_suggestions_for_slide, pick_game_for_slide
from .knowledge import LearningObjective
from .page_media import motion_data_url, picture_data_url
from .studio_languages import normalize_language, tts_needs_fallback
from .types import CategoryId, CourseSlide, StudioCourse

# Staggered continue / come-back-later from PR #484 (15–20 min blocks).
DEFAULT_TRIAL_MINUTES = 18
DEFAULT_SOFT_LIMIT_MINUTES = 18


class SegmentKind(str, Enum):
    LESSON = "lesson"
    GAME = "game"
    VIDEO = "video"
    ANIMATION = "animation"
    QUIZ = "quiz"
    PRONUNCIATION = "pronunciation"
    RECALL = "recall"
    REMEMBER = "remember"
    EXPLANATION = "explanation"
    ACTIVITY = "activity"


class CourseSegmentSnippet(BaseModel):
    kind: SegmentKind
    title: str
    body: str = ""
    narration: str = ""
    activity: str = ""
    examples: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ComposeCourseRequest(BaseModel):
    title: str = "Trial composed course"
    language: str = "en"
    segments: list[CourseSegmentSnippet] = Field(default_factory=list)
    course_id: str | None = None
    category: CategoryId = CategoryId.OTHER
    estimated_minutes: int = DEFAULT_TRIAL_MINUTES


# Small curated trial strings so a demo works offline in es/km without xAI.
_TRIAL_CURATED: dict[str, dict[str, tuple[str, str]]] = {
    "es": {
        "Welcome": ("Bienvenido", "Empecemos juntos."),
        "Quick check": ("Comprobación rápida", "¿Recuerdas la idea principal?"),
        "Say it aloud": ("Dilo en voz alta", "Repite la frase conmigo."),
        "Things to remember": ("Cosas para recordar", "Guarda estas ideas importantes."),
    },
    "km": {
        "Welcome": ("សូមស្វាគមន៍", "ចាប់ផ្តើមរៀនជាមួយគ្នា។"),
        "Quick check": ("ពិនិត្យរហ័ស", "តើអ្នកចងចាំគំរូដើមទេ?"),
        "Say it aloud": ("និយាយឱ្យឮ", "សូមធ្វើតាមខ្ញុំ។"),
        "Things to remember": ("អ្វីដែលត្រូវចងចាំ", "រក្សាគំនិតសំខាន់ទាំងនេះ។"),
    },
}


def resolve_spoken_text(text: str, language: str) -> tuple[str, str, str]:
    """Return (text, spoken_language, translation_source)."""
    lang = normalize_language(language)
    raw = (text or "").strip()
    if not raw:
        return "", lang if lang == "en" else "en", "empty"
    if lang == "en":
        return raw, "en", "english"
    curated = _TRIAL_CURATED.get(lang, {})
    if raw in curated:
        translated, _ = curated[raw]
        return translated, lang, "curated"
    # Honest fallback — never speak English with a foreign voice tag.
    if tts_needs_fallback(lang):
        return raw, "en", "english"
    return raw, "en", "english"


def _localized_segment(seg: CourseSegmentSnippet, language: str) -> tuple[CourseSegmentSnippet, str, str]:
    title, spoken, src = resolve_spoken_text(seg.title, language)
    body, body_spoken, body_src = resolve_spoken_text(seg.body or title, language)
    narr, narr_spoken, narr_src = resolve_spoken_text(
        seg.narration or body or title, language
    )
    spoken_lang = spoken if spoken == body_spoken == narr_spoken else (
        spoken if spoken != "en" else (body_spoken if body_spoken != "en" else narr_spoken)
    )
    source = src if src != "english" else (body_src if body_src != "english" else narr_src)
    localized = CourseSegmentSnippet(
        kind=seg.kind,
        title=title,
        body=body,
        narration=narr,
        activity=seg.activity,
        examples=list(seg.examples),
        tags=[*seg.tags, f"translation:{source}"],
    )
    return localized, spoken_lang, source


def _slide_from_segment(
    index: int,
    seg: CourseSegmentSnippet,
    spoken_language: str,
) -> CourseSlide:
    key = f"trial.{seg.kind.value}.{index:02d}"
    body = seg.body or seg.title
    narration = seg.narration or body
    slide = CourseSlide(
        index=index,
        slide_key=key,
        title=seg.title,
        body=body,
        narration=narration,
        spoken_language=spoken_language,
        activity_prompt=seg.activity,
        examples=list(seg.examples),
        tags=[seg.kind.value, *seg.tags],
        picture_url=picture_data_url(
            title=seg.title[:48], symbol=seg.kind.value[:1].upper(), color="#38bdf8"
        ),
        video_url=motion_data_url(
            title=seg.title[:48], symbol=seg.kind.value[:1].upper(), color="#38bdf8"
        ),
        video_caption=seg.title,
        modalities=_modalities_for_kind(seg.kind),
    )
    objective = LearningObjective(
        objective_id=f"{key}.obj",
        course_id="trial",
        title=seg.title,
        slide_indexes=[index],
    )
    if seg.kind in {SegmentKind.QUIZ, SegmentKind.RECALL}:
        quiz = build_pop_quiz_for_slide(slide, objective)
        slide.quiz_spec = quiz.model_dump(mode="json")
    if seg.kind is SegmentKind.GAME:
        game = pick_game_for_slide(slide, objective_id=objective.objective_id, rotate_index=index)
        slide.game_spec = game.model_dump(mode="json")
    if seg.kind is SegmentKind.PRONUNCIATION:
        slide.activity_prompt = seg.activity or "Repeat the phrase clearly after Theodore."
        slide.tags.append("pronunciation")
    if seg.kind is SegmentKind.REMEMBER:
        slide.tags.append("remember")
    if seg.kind is SegmentKind.EXPLANATION:
        slide.tags.append("explanation")
    _ = media_suggestions_for_slide(slide)
    if seg.kind is SegmentKind.GAME and not slide.game_spec:
        slide.game_spec = build_match_term_game(slide).model_dump(mode="json")
    return slide


def _modalities_for_kind(kind: SegmentKind) -> list[str]:
    if kind is SegmentKind.VIDEO:
        return ["video", "text", "audio"]
    if kind is SegmentKind.ANIMATION:
        return ["animation", "text", "audio"]
    if kind is SegmentKind.GAME:
        return ["game", "text"]
    if kind in {SegmentKind.QUIZ, SegmentKind.RECALL}:
        return ["quiz", "text"]
    if kind is SegmentKind.PRONUNCIATION:
        return ["audio", "text", "activity"]
    return ["text", "image", "audio"]


def compose_course_from_segments(req: ComposeCourseRequest) -> StudioCourse:
    lang = normalize_language(req.language)
    segments = req.segments or default_trial_segments()
    slides: list[CourseSlide] = []
    sources: set[str] = set()
    for i, seg in enumerate(segments):
        localized, spoken_lang, source = _localized_segment(seg, lang)
        sources.add(source)
        slides.append(_slide_from_segment(i, localized, spoken_lang))
    course_id = (req.course_id or f"trial-{uuid.uuid4().hex[:10]}").strip()
    spoken_summary = lang if lang in sources and "english" not in sources else (
        lang if all(s.spoken_language == lang for s in slides) else "en"
    )
    return StudioCourse(
        course_id=course_id,
        title=req.title,
        category=req.category,
        language=lang,
        estimated_minutes=req.estimated_minutes or DEFAULT_TRIAL_MINUTES,
        slides=slides,
        profile_adaptations={
            "spoken_language": spoken_summary,
            "translation_sources": sorted(sources),
            "composed": True,
            "soft_limit_minutes": DEFAULT_SOFT_LIMIT_MINUTES,
        },
        created_at_ms=int(time.time() * 1000),
        status="ready",
    )


def default_trial_segments() -> list[CourseSegmentSnippet]:
    """End-to-end trial sequence covering every behavioral segment kind."""
    return [
        CourseSegmentSnippet(
            kind=SegmentKind.LESSON,
            title="Welcome",
            body="Today we practice one idea at a time with pictures, motion, and play.",
            narration="Welcome! We will move through a short lesson, a game, a video, and a quiz.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.EXPLANATION,
            title="Explain the idea",
            body="A good learner pauses, looks, listens, then tries.",
            narration="Let me explain how we will learn together today.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.VIDEO,
            title="Watch the motion clip",
            body="See the motion card while Theodore narrates.",
            narration="Watch the short animation and notice the main idea.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.GAME,
            title="Play a quick game",
            body="Match the term to lock in the idea.",
            activity="Tap the best answer or say it aloud.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.QUIZ,
            title="Quick check",
            body="Do you remember the main idea?",
            narration="Let's check what you remember with a tiny quiz.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.PRONUNCIATION,
            title="Say it aloud",
            body="Repeat the key phrase clearly.",
            narration="Listen, then say the phrase in your own voice.",
            activity="Pronunciation check — repeat after Theodore.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.RECALL,
            title="Do you remember this?",
            body="Recall the example from the lesson.",
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.REMEMBER,
            title="Things to remember",
            body="Keep these three ideas with you after class.",
            examples=["Pause and look", "Try the activity", "Ask Theodore if stuck"],
        ),
        CourseSegmentSnippet(
            kind=SegmentKind.ACTIVITY,
            title="Try it yourself",
            body="Stand up, stretch, and teach the idea to a stuffed animal or mirror.",
            activity="Movement break — 30 seconds.",
        ),
    ]


def trial_demo_plan(language: str = "en") -> dict[str, Any]:
    course = compose_course_from_segments(
        ComposeCourseRequest(title="Trial demo course", language=language)
    )
    return {
        "course": course.model_dump(mode="json"),
        "segment_count": len(course.slides),
        "segment_kinds": [s.tags[0] if s.tags else "lesson" for s in course.slides],
        "spoken_language": course.profile_adaptations.get("spoken_language"),
        "translation_sources": course.profile_adaptations.get("translation_sources"),
        "estimated_minutes": course.estimated_minutes,
        "soft_limit_minutes": DEFAULT_SOFT_LIMIT_MINUTES,
    }
