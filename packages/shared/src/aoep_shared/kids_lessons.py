"""Kids picture-lesson content shared by web and mobile.

The 8 early-learning adventures used to live only in the web bundle
(``apps/web/app/lib/kidsLearning.ts``), which is why the mobile Kids section
could list them but never play them. Serving them from here gives both clients
one source of truth instead of a second hand-maintained copy.

Each lesson is a short sequence of scenes; a scene shows emoji "pictures" with
optional labels, then asks one multiple-choice question.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_FILE = Path(__file__).with_name("data") / "kids_lessons.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict[str, Any]]:
    try:
        raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, dict)}


def kids_lesson_ids() -> list[str]:
    return sorted(_load())


def get_kids_lesson(course_id: str) -> dict[str, Any] | None:
    """One lesson by course id, or None when the id is not a kids lesson."""
    return _load().get((course_id or "").strip())


def list_kids_lessons() -> list[dict[str, Any]]:
    """Every lesson, ordered by title so clients render a stable list."""
    return sorted(_load().values(), key=lambda item: str(item.get("title", "")))
