"""A slide for a question the course has not already written down.

Live talk can jump to an existing page when the words overlap. A question
such as disability placards during driver's ed often uses words no slide
contains. This builds a short example card and, when a search key is set,
attaches live sources. Without a key it still shows the official handbook
for a California driver course.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .topic_cover import example_card_svg, tokens

_QUESTION = re.compile(
    r"\?|\b(what|how|why|when|where|who|which|example|examples|law|laws|"
    r"rule|rules|restriction|restrictions|placard|placards|permit)\b",
    re.IGNORECASE,
)
_GENERIC = frozenset(
    """
    rule rules law laws example examples question questions right sign signs
    about tell show explain give
    """.split()
)
_DRIVING = frozenset(
    """
    disability disabled handicap handicapped placard placards wheelchair
    parking restriction restrictions legal dmv license permit driver drivers
    driving vehicle car road traffic medical vision seizure insulin passenger
    senior citation insurance brake signal speed pedestrian crosswalk
    """.split()
)
_CA_HANDBOOK = {
    "title": "California Driver Handbook",
    "url": "https://www.dmv.ca.gov/portal/handbook/california-driver-handbook/",
    "snippet": (
        "California's handbook is the source for licenses, restrictions, "
        "and parking placards. Confirm the current page before a test."
    ),
}


def asks_for_material(text: str) -> bool:
    said = " ".join((text or "").split())
    if len(said) < 8:
        return False
    return bool(_QUESTION.search(said))


def _category(course: Any) -> str:
    raw = getattr(course, "category", "") or ""
    return str(getattr(raw, "value", raw) or "")


def _subject_words(course: Any) -> set[str]:
    words = set(tokens(getattr(course, "title", "") or ""))
    if _category(course) == "driver_education" or _is_driving_course(course):
        words |= _DRIVING
    for slide in getattr(course, "slides", []) or []:
        words |= tokens(getattr(slide, "title", "") or "")
    return words


def _is_driving_course(course: Any) -> bool:
    title = (getattr(course, "title", "") or "").lower()
    adaptations = getattr(course, "profile_adaptations", None) or {}
    track = str(adaptations.get("track") or "").lower()
    return (
        _category(course) == "driver_education"
        or track == "ca_dmv_permit"
        or "dmv" in title
        or "driver" in title
    )


def question_fits_course(course: Any, text: str) -> bool:
    """True when the learner is asking about this subject, not small talk."""
    if not asks_for_material(text):
        return False
    query = tokens(text)
    if not query or query <= {"weather", "hello", "thanks", "thank"}:
        return False
    specific = (query & _subject_words(course)) - _GENERIC
    if specific:
        return True
    if _is_driving_course(course) and (query & _DRIVING):
        return True
    return False


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _title_for(question: str) -> str:
    title = question.strip().rstrip("?").strip()
    title = title[:1].upper() + title[1:] if title else "Your question"
    return _clip(title, 72)


def _worked_example(question: str, course: Any) -> list[str]:
    low = (question or "").lower()
    if any(word in low for word in ("placard", "disability", "disabled", "handicap")):
        return [
            "The placard belongs to the person, not the car.",
            "Use the marked space only while that person is in the car.",
            "Stops, signals, and speed limits still apply.",
        ]
    course_title = getattr(course, "title", "") or "this course"
    return [
        f"Pick one trip in {course_title}.",
        "Name the rule your question is about.",
        "Say what you do, and what you do not do.",
    ]


def official_sources(course: Any) -> list[dict[str, str]]:
    if _is_driving_course(course):
        adaptations = getattr(course, "profile_adaptations", None) or {}
        track = str(adaptations.get("track") or "")
        title = (getattr(course, "title", "") or "").lower()
        if track == "ca_dmv_permit" or "california" in title or "ca dmv" in title or "dmv" in title:
            return [dict(_CA_HANDBOOK)]
    return []


def _search_live(query: str) -> list[dict[str, str]]:
    try:
        from aoep_shared.config import load_config
        from aoep_shared.providers.search import available_engines
    except Exception:
        return []
    try:
        engines = [
            engine
            for engine in available_engines(load_config())
            if getattr(engine, "engine", "") != "mock"
        ]
    except Exception:
        return []
    if not engines:
        return []

    def _run() -> list[dict[str, str]]:
        hits = engines[0].search(query, max_results=3)
        rows = []
        for hit in hits:
            url = str(getattr(hit, "url", "") or "")
            if not url.startswith("https://"):
                continue
            rows.append(
                {
                    "title": _clip(str(getattr(hit, "title", "") or url), 120),
                    "url": url,
                    "snippet": _clip(str(getattr(hit, "snippet", "") or ""), 280),
                }
            )
        return rows

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run).result(timeout=2.5)
    except Exception:
        return []


def lookup_question_sources(course: Any, question: str) -> list[dict[str, str]]:
    """Live results first, then the official page for this course."""
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in [*_search_live(f"{getattr(course, 'title', '')} {question}"), *official_sources(course)]:
        url = row.get("url") or ""
        if not url.startswith("https://") or url in seen:
            continue
        seen.add(url)
        merged.append(row)
        if len(merged) == 3:
            break
    return merged


def build_question_slide(
    course: Any,
    question: str,
    sources: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Return a screen card, or None when the question is not about this course."""
    if not question_fits_course(course, question):
        return None
    rows = list(sources or [])
    title = _title_for(question)
    examples = _worked_example(question, course)
    course_title = getattr(course, "title", "") or "this course"
    snippet = next((row.get("snippet") or "" for row in rows if row.get("snippet")), "")
    parts = []
    if snippet:
        parts.append(snippet)
    parts.append(" ".join(examples))
    parts.append(
        f"This stays inside {course_title}. Rules change, so read a source on this page before a test."
    )
    body = " ".join(part.strip() for part in parts if part.strip())
    return {
        "title": title,
        "body": body,
        "examples": examples,
        "sources": rows,
        "example_svg": example_card_svg(title, examples),
    }


SourceLookup = Callable[[Any, str], list[dict[str, str]]]
