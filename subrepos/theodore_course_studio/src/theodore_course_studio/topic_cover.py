"""Match a live conversation to a course slide and measure coverage.

Learners may talk about any section, in any order. A topic counts as covered
when the conversation lands on that slide. Percent complete is covered slides
divided by the slides in the course.
"""

from __future__ import annotations

import html
import re
from typing import Any

_STOP = frozenset(
    """
    the a an of to and or in on for with your this that is are was were be been
    it we you i they them our their from into about what when where how why who
    can could would should just like have has had not but
    """.split()
)


def tokens(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9']{3,}", (text or "").lower())
        if word not in _STOP
    }


def _slide_text(slide: Any) -> str:
    return " ".join(
        [
            getattr(slide, "title", "") or "",
            getattr(slide, "body", "") or "",
            getattr(slide, "narration", "") or "",
            getattr(slide, "activity_prompt", "") or "",
            " ".join(getattr(slide, "examples", None) or []),
            " ".join(getattr(slide, "tags", None) or []),
        ]
    )


def match_slide(course: Any, text: str) -> int | None:
    """Return the slide index the utterance is about, or None when it is off-topic."""
    query = tokens(text)
    if not query:
        return None
    best_index: int | None = None
    best_score = 0
    for slide in course.slides:
        hay = tokens(_slide_text(slide))
        title = tokens(getattr(slide, "title", "") or "")
        score = len(query & hay) + (2 * len(query & title))
        if score > best_score:
            best_score = score
            best_index = slide.index
    needed = 1 if len(query) == 1 else 2
    if best_score < needed:
        return None
    return best_index


def completion_percent(course: Any, completed: list[int] | set[int]) -> int:
    indexes = {slide.index for slide in course.slides}
    if not indexes:
        return 0
    done = len(indexes.intersection(completed))
    return round(100 * done / len(indexes))


def example_lines(slide: Any) -> list[str]:
    """Use authored examples, or one line drawn from the slide itself."""
    authored = [
        line.strip()
        for line in (getattr(slide, "examples", None) or [])
        if isinstance(line, str) and line.strip()
    ]
    if authored:
        return authored[:3]
    body = (getattr(slide, "body", "") or getattr(slide, "narration", "") or "").strip()
    sentence = re.split(r"(?<=[.!?])\s+", body)[0].strip() if body else ""
    if sentence:
        return [sentence[:180]]
    title = (getattr(slide, "title", "") or "").strip()
    return [title] if title else []


def example_card_svg(title: str, lines: list[str]) -> str:
    """A small animated example card when the slide has no picture of its own."""

    def row(text: str) -> str:
        return html.escape((text or "").strip())[:90]

    title_row = row(title or "Example")
    body = "".join(
        f'<text x="36" y="{96 + index * 36}" font-size="18" fill="#1e3a5f">{row(line)}</text>'
        for index, line in enumerate(lines[:3])
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img">'
        "<style>@keyframes example-in{from{opacity:0;transform:translateY(12px)}"
        "to{opacity:1;transform:none}}</style>"
        '<rect width="640" height="360" rx="28" fill="#eef2ff"/>'
        '<rect x="20" y="20" width="600" height="320" rx="20" fill="#ffffff" '
        'stroke="#6366f1" stroke-width="3" style="animation:example-in .6s ease"/>'
        f'<text x="36" y="58" font-size="24" font-weight="700" fill="#312e81">{title_row}</text>'
        f"{body}</svg>"
    )


def slide_has_art(slide: Any) -> bool:
    return bool(
        getattr(slide, "storyboard_svg", "")
        or getattr(slide, "picture_url", "")
        or getattr(slide, "video_url", "")
        or getattr(slide, "visual_cues", None)
        or getattr(slide, "visual_layers", None)
    )
