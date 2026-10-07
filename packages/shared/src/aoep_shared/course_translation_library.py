"""Pre-translated course library.

The batch pipeline writes one JSON file per course and language. Drive Mode
and the voice agent read that file instead of translating again. A lookup
stays inside one class: the course id, or the same title inside the same
category.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from .languages import SUPPORTED_LANGUAGES, normalize_language

# English is the source. The other 26 supported languages are translated ahead of time.
TARGET_LANGUAGES: tuple[str, ...] = tuple(
    code for code in SUPPORTED_LANGUAGES if code != "en"
)

_INDEX = "index.json"
_LOCK = threading.Lock()


def library_dir() -> Path:
    raw = os.environ.get("AOEP_COURSE_TRANSLATION_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache" / "aoep" / "course_translations"


def safe_course_id(course_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (course_id or "").strip()).strip("-._")
    return cleaned or "course"


def normalize_label(text: str) -> str:
    """Compare titles and categories without punctuation or the audio suffix."""
    value = (text or "").casefold()
    value = value.replace("(audio)", " ").replace("（音频）", " ")
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def translation_path(course_id: str, language: str, root: Path | None = None) -> Path:
    code = normalize_language(language) or "en"
    return (root or library_dir()) / safe_course_id(course_id) / f"{code}.json"


def save_translation(record: dict[str, Any], root: Path | None = None) -> Path:
    """Write one course language and update the title index."""
    course_id = str(record.get("course_id") or "").strip()
    language = normalize_language(str(record.get("language") or ""))
    if not course_id or not language:
        raise ValueError("course_id and a supported language are required")
    payload = {
        "course_id": course_id,
        "title": str(record.get("title") or "").strip(),
        "category": str(record.get("category") or "").strip(),
        "source_language": "en",
        "language": language,
        "source": str(record.get("source") or "batch"),
        "segments": [
            {
                "heading": str(row.get("heading") or "").strip(),
                "text": str(row.get("text") or "").strip(),
                "kind": str(row.get("kind") or "narration"),
            }
            for row in record.get("segments") or []
            if str(row.get("heading") or "").strip() and str(row.get("text") or "").strip()
        ],
    }
    if not payload["segments"]:
        raise ValueError("a translation needs at least one segment")
    path = translation_path(course_id, language, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, payload)
    _remember(payload, root or library_dir())
    return path


def load_translation(
    course_id: str, language: str, root: Path | None = None
) -> dict[str, Any] | None:
    path = translation_path(course_id, language, root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("segments"):
        return None
    return data


def find_translation(
    *,
    course_id: str = "",
    title: str = "",
    category: str = "",
    language: str = "",
    root: Path | None = None,
) -> dict[str, Any] | None:
    """Load the pre-translated class, refusing a title that belongs to another category."""
    base = root or library_dir()
    code = normalize_language(language)
    if not code:
        return None
    if course_id:
        return load_translation(course_id, code, base)
    wanted_title = normalize_label(title)
    wanted_category = normalize_label(category)
    if not wanted_title:
        return None
    index = _read_index(base)
    for row in index.get("courses") or []:
        if normalize_label(str(row.get("title") or "")) != wanted_title:
            continue
        row_category = normalize_label(str(row.get("category") or ""))
        if wanted_category and row_category and wanted_category != row_category:
            continue
        found = load_translation(str(row.get("course_id") or ""), code, base)
        if found:
            return found
    return None


def reference_for_class(
    *,
    course_id: str = "",
    title: str = "",
    category: str = "",
    language: str = "",
    query: str = "",
    limit_chars: int = 1600,
    root: Path | None = None,
) -> dict[str, Any]:
    """Passages from this class only.

    ``hit`` is true when this class has a pre-translated file. Matching
    words are preferred. Otherwise the opening passages are the training
    source, and the voice agent may search online only inside this class.
    """
    record = find_translation(
        course_id=course_id,
        title=title,
        category=category,
        language=language,
        root=root,
    )
    if not record:
        return {"hit": False, "text": "", "course_id": "", "language": language}
    passages, _matched = _select(record.get("segments") or [], query)
    if not passages:
        return {
            "hit": False,
            "text": "",
            "course_id": record.get("course_id") or "",
            "language": record.get("language") or language,
        }
    chunks: list[str] = []
    used = 0
    for row in passages:
        block = f"{row['heading']}. {row['text']}"
        if used and used + len(block) > limit_chars:
            break
        chunks.append(block)
        used += len(block)
    return {
        "hit": True,
        "text": "\n\n".join(chunks),
        "course_id": record.get("course_id") or "",
        "language": record.get("language") or language,
    }


def _select(segments: list[dict[str, Any]], query: str) -> tuple[list[dict[str, str]], bool]:
    rows = [
        {"heading": str(row.get("heading") or ""), "text": str(row.get("text") or "")}
        for row in segments
        if str(row.get("heading") or "").strip() and str(row.get("text") or "").strip()
    ]
    tokens = [token for token in normalize_label(query).split() if len(token) > 2]
    if not tokens:
        return rows[:4], bool(rows)
    scored: list[tuple[int, dict[str, str]]] = []
    for row in rows:
        hay = normalize_label(f"{row['heading']} {row['text']}")
        score = sum(1 for token in tokens if token in hay)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = [row for _score, row in scored[:4]]
    if hits:
        return hits, True
    # The class is in the library even when this question uses different words.
    # The voice agent then keeps these passages and may search only inside the class.
    return rows[:4], False


def _remember(record: dict[str, Any], root: Path) -> None:
    with _LOCK:
        index = _read_index(root)
        previous = next(
            (
                row
                for row in index.get("courses") or []
                if str(row.get("course_id") or "") == record["course_id"]
            ),
            {},
        )
        languages = sorted(
            {str(code) for code in previous.get("languages") or []} | {record["language"]}
        )
        courses = [
            row
            for row in index.get("courses") or []
            if str(row.get("course_id") or "") != record["course_id"]
        ]
        courses.append(
            {
                "course_id": record["course_id"],
                "title": record["title"],
                "category": record["category"],
                "languages": languages,
            }
        )
        _atomic_write(root / _INDEX, {"courses": courses})


def _read_index(root: Path) -> dict[str, Any]:
    path = root / _INDEX
    if not path.is_file():
        return {"courses": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"courses": []}
    if not isinstance(data, dict):
        return {"courses": []}
    return data


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
