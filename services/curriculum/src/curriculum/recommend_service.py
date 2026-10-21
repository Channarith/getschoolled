"""Foresight /recommend helpers — cold-start defaults and safe course features."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Sequence

from aoep_shared.adaptation_line import style_token
from aoep_shared.foresight import CourseFeature, LearnerForesight, StudentProfile
from aoep_shared.learning_profile import decode_profile_score

from .catalog import Course

logger = logging.getLogger(__name__)

_COLD_MASTERY_MAX = 0.05


@dataclass
class LearnerHints:
    """Survey and in-class signals. Survey answers are not rewritten."""

    profile_score: str = ""
    primary_style: str = ""
    pace: str = ""
    session_length: str = ""
    reading_level: str = ""
    live_style: str = ""


def is_cold_start(profile: StudentProfile) -> bool:
    """True when the learner has no meaningful history (first visit / new profile)."""
    if profile.completed_course_ids or profile.interests:
        return False
    if not profile.mastery:
        return True
    return all(float(v) <= _COLD_MASTERY_MAX for v in profile.mastery.values())


def course_skills(course: Course) -> List[str]:
    """Normalize tags/category into skill strings for Foresight."""
    skills: List[str] = []
    for raw in course.tags or []:
        if isinstance(raw, str) and raw.strip():
            skills.append(raw.strip().lower())
    if skills:
        return skills
    for fallback in (course.category, course.subject, "general"):
        if fallback and str(fallback).strip():
            return [str(fallback).strip().lower()]
    return ["general"]


def courses_to_features(courses: Sequence[Course]) -> List[CourseFeature]:
    return [
        CourseFeature(
            course_id=c.course_id,
            title=c.title or c.course_id,
            skills=course_skills(c),
            level=c.level or "beginner",
            category=(c.category or c.subject or "general").lower(),
        )
        for c in courses
        if c.course_id
    ]


def _decoded_profile(hints: LearnerHints) -> dict:
    raw = (hints.profile_score or "").strip()
    if not raw:
        return {}
    try:
        return decode_profile_score(raw)
    except ValueError:
        return {}


def resolved_hints(hints: LearnerHints) -> dict[str, str]:
    """Live emphasis wins over the survey. Explicit fields win over the score."""
    decoded = _decoded_profile(hints)
    if (hints.live_style or "").strip():
        style = style_token(hints.live_style)
    elif (hints.primary_style or "").strip():
        style = style_token(hints.primary_style)
    else:
        style = style_token(str(decoded.get("primary_style") or ""))
    pace = (hints.pace or str(decoded.get("pace") or "") or "moderate").strip().lower()
    session = (hints.session_length or str(decoded.get("session_length") or "") or "medium").strip().lower()
    reading = (hints.reading_level or str(decoded.get("reading_level") or "") or "intermediate").strip().lower()
    return {"style": style, "pace": pace, "session_length": session, "reading_level": reading}


def _style_match(course: Course, style: str) -> bool | None:
    if style in {"", "balanced"}:
        return None
    fmt = (course.media_format or "video").strip().lower()
    if style == "visual":
        return fmt in {"video", "interactive"}
    if style == "listening":
        return fmt == "audio"
    if style == "reading":
        return fmt == "text"
    if style == "practice":
        return bool(course.hands_on)
    return None


def _prefers_easy(pace: str, reading: str) -> bool:
    return pace == "slow" or reading == "beginner"


def _prefers_hard(pace: str, reading: str) -> bool:
    return pace == "fast" or reading == "advanced"


def _continues(course: Course, finished: Sequence[Course]) -> bool:
    tags = {t.strip().lower() for t in (course.tags or []) if t and t.strip()}
    category = (course.category or course.subject or "").strip().lower()
    for done in finished:
        done_tags = {t.strip().lower() for t in (done.tags or []) if t and t.strip()}
        if tags and tags & done_tags:
            return True
        done_category = (done.category or done.subject or "").strip().lower()
        if category and category == done_category and category not in {"general"}:
            return True
    return False


def _profile_factor(course: Course, hints: LearnerHints, finished: Sequence[Course]) -> float:
    resolved = resolved_hints(hints)
    factor = 1.0
    matched = _style_match(course, resolved["style"])
    if matched is True:
        factor *= 1.35
    elif matched is False:
        factor *= 0.75
    duration = int(course.duration_min or 0)
    if resolved["session_length"] == "short":
        if duration and duration <= 15:
            factor *= 1.2
        elif duration > 30:
            factor *= 0.85
    elif resolved["session_length"] == "long" and duration >= 25:
        factor *= 1.15
    level = (course.level or "beginner").strip().lower()
    if _prefers_easy(resolved["pace"], resolved["reading_level"]):
        if level == "beginner":
            factor *= 1.25
        elif level == "advanced":
            factor *= 0.7
    elif _prefers_hard(resolved["pace"], resolved["reading_level"]):
        if level in {"intermediate", "advanced"}:
            factor *= 1.2
        elif level == "beginner":
            factor *= 0.85
    if _continues(course, finished):
        factor *= 1.15
    return factor


def reason_key(
    course: Course,
    hints: LearnerHints,
    finished: Sequence[Course],
    *,
    covers_gap: bool,
) -> tuple[str, str]:
    """Plain-language key. A skill gap outranks a 'continues' note."""
    style = resolved_hints(hints)["style"]
    if covers_gap:
        return "rec.becauseGap", style
    if _continues(course, finished):
        return "rec.becauseFinished", style
    if _style_match(course, style) is True:
        return "rec.becauseStyle", style
    duration = int(course.duration_min or 0)
    if resolved_hints(hints)["session_length"] == "short" and duration and duration <= 15:
        return "rec.becauseShort", style
    return "rec.becauseFirst", style


def _finished_courses(profile: StudentProfile, catalog_courses: Sequence[Course]) -> list[Course]:
    wanted = set(profile.completed_course_ids or [])
    return [c for c in catalog_courses if c.course_id in wanted]


def _rank_score(course: Course, hints: LearnerHints, finished: Sequence[Course], base: float) -> float:
    resolved = resolved_hints(hints)
    score = float(base) * _profile_factor(course, hints, finished)
    level = (course.level or "beginner").strip().lower()
    if not _prefers_hard(resolved["pace"], resolved["reading_level"]) and level == "beginner":
        score += 0.05
    score += min(int(course.popularity or 0), 1000) / 100000.0
    return round(score, 4)


def starter_payload(
    profile: StudentProfile,
    catalog_courses: Sequence[Course],
    *,
    top_n: int = 5,
    hints: LearnerHints | None = None,
) -> dict:
    """First classes, ordered by the learning profile when one is present."""
    hints = hints or LearnerHints()
    finished = _finished_courses(profile, catalog_courses)
    ranked = sorted(
        catalog_courses,
        key=lambda c: _rank_score(c, hints, finished, 1.0),
        reverse=True,
    )
    picks = ranked[:top_n]
    return {
        "student_id": profile.student_id,
        "difficulty": "beginner",
        "gaps": [],
        "cold_start": True,
        "recommendations": [
            {
                "course_id": c.course_id,
                "title": c.title or c.course_id,
                "score": _rank_score(c, hints, finished, 1.0),
                "covers_gaps": [],
                "reason": reason_key(c, hints, finished, covers_gap=False)[0],
                "reason_style": reason_key(c, hints, finished, covers_gap=False)[1],
            }
            for c in picks
        ],
        "relational_map": {
            "nodes": [
                {"id": f"student:{profile.student_id}", "kind": "student"},
                *[{"id": f"course:{c.course_id}", "kind": "course"} for c in picks],
            ],
            "edges": [
                {"src": f"student:{profile.student_id}", "dst": f"course:{c.course_id}",
                 "rel": "starter", "weight": 1.0}
                for c in picks
            ],
        },
    }


def _annotate(out: dict, profile: StudentProfile, catalog_courses: Sequence[Course], hints: LearnerHints) -> dict:
    """Re-rank Foresight picks with style, pace, length, and finished-course affinity."""
    by_id = {c.course_id: c for c in catalog_courses}
    finished = _finished_courses(profile, catalog_courses)
    recs = list(out.get("recommendations") or [])
    for rec in recs:
        course = by_id.get(rec.get("course_id"))
        covers = bool(rec.get("covers_gaps"))
        if course is None:
            rec["reason"] = "rec.becauseGap" if covers else "rec.becauseFirst"
            rec["reason_style"] = resolved_hints(hints)["style"]
            continue
        base = float(rec.get("score") or 1.0)
        rec["score"] = _rank_score(course, hints, finished, base)
        key, style = reason_key(course, hints, finished, covers_gap=covers)
        rec["reason"] = key
        rec["reason_style"] = style
    recs.sort(key=lambda rec: float(rec.get("score") or 0), reverse=True)
    out["recommendations"] = recs
    return out


def run_recommend(
    profile: StudentProfile,
    catalog_courses: Sequence[Course],
    *,
    top_n: int = 5,
    hints: LearnerHints | None = None,
) -> dict:
    """Safe recommend: cold-start defaults, Foresight when history exists, never raises."""
    hints = hints or LearnerHints()
    if is_cold_start(profile):
        return starter_payload(profile, catalog_courses, top_n=top_n, hints=hints)

    features = courses_to_features(catalog_courses)
    skills = sorted({s for f in features for s in f.skills})
    if not skills:
        return starter_payload(profile, catalog_courses, top_n=top_n, hints=hints)

    try:
        lf = LearnerForesight(skills)
        out = lf.predict(profile, features)
        out["cold_start"] = False
        recs = out.get("recommendations") or []
        if not recs:
            return starter_payload(profile, catalog_courses, top_n=top_n, hints=hints)
        out = _annotate(out, profile, catalog_courses, hints)
        out["recommendations"] = out["recommendations"][:top_n]
        return out
    except Exception as exc:
        logger.exception("Foresight recommend failed; falling back to starters (%s)", exc)
        out = starter_payload(profile, catalog_courses, top_n=top_n, hints=hints)
        out["fallback"] = True
        return out
