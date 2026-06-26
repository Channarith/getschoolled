"""Foresight /recommend helpers — cold-start defaults and safe course features."""

from __future__ import annotations

import logging
from typing import List, Sequence

from aoep_shared.foresight import CourseFeature, LearnerForesight, StudentProfile

from .catalog import Course

logger = logging.getLogger(__name__)

_COLD_MASTERY_MAX = 0.05


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


def starter_payload(
    profile: StudentProfile,
    catalog_courses: Sequence[Course],
    *,
    top_n: int = 5,
) -> dict:
    """Generic defaults for new learners: popular beginner-friendly catalog picks."""
    ranked = sorted(
        catalog_courses,
        key=lambda c: (
            0 if (c.level or "beginner") == "beginner" else 1,
            -(c.popularity or 0),
            -(c.created_at or 0),
        ),
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
                "score": 1.0,
                "covers_gaps": [],
                "reason": "Popular starter pick — great for your first classes",
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


def run_recommend(
    profile: StudentProfile,
    catalog_courses: Sequence[Course],
    *,
    top_n: int = 5,
) -> dict:
    """Safe recommend: cold-start defaults, Foresight when history exists, never raises."""
    if is_cold_start(profile):
        return starter_payload(profile, catalog_courses, top_n=top_n)

    features = courses_to_features(catalog_courses)
    skills = sorted({s for f in features for s in f.skills})
    if not skills:
        return starter_payload(profile, catalog_courses, top_n=top_n)

    try:
        lf = LearnerForesight(skills)
        out = lf.predict(profile, features)
        out["cold_start"] = False
        recs = out.get("recommendations") or []
        if not recs:
            return starter_payload(profile, catalog_courses, top_n=top_n)
        out["recommendations"] = recs[:top_n]
        return out
    except Exception as exc:
        logger.exception("Foresight recommend failed; falling back to starters (%s)", exc)
        out = starter_payload(profile, catalog_courses, top_n=top_n)
        out["fallback"] = True
        return out
