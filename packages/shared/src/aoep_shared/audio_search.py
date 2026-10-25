"""Search index for the audio ("On the Go") courses: which courses have a SHIPPABLE translation in which language.

A language is listed for a course only when the library file is the right shape (same segments as today's English), is a
translation of today's English (provenance source hash) and still passes the v2 validator (``translation_v2.is_current``).
Held, rejected, stale, wrongly filed or partial files are never listed, so the picker never offers a course it would read in the
wrong language. The verdicts are cached per file (path, mtime, size), so a search is cheap and a newly written file shows up on the
next request.

Narration is live text-to-speech in the voice the learner picked: ``audio_mode`` says so (there are no per-course pre-rendered clips).
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import translation_v2 as v2
from .course_translation_library import library_dir, load_translation, normalize_translation_language, translation_path

_CACHE: Dict[Tuple[str, str, str], Tuple[Tuple[int, int, str], bool, str]] = {}
_LOCK = threading.Lock()


def language_family(code: str) -> str:
    """"en-GB" -> "en", "zh-HK" -> "yue", "fil" -> "tl", "pt_BR" -> "pt". "" when the code is empty."""
    c = (code or "").strip().lower().replace("_", "-")
    if not c:
        return ""
    if c in {"yue", "cantonese"} or c.startswith(("yue-", "zh-hk", "zh-mo")):
        return "yue"
    if c == "singlish":
        return "en"
    return normalize_translation_language(c.split("-")[0]) or c.split("-")[0]


def _file_key(path: Path) -> Tuple[int, int, str]:
    try:
        st = path.stat()
    except OSError:
        return (0, 0, "")
    return (st.st_mtime_ns, st.st_size, str(path))


def shippable(source: "v2.CourseSource", lang: str, root: Optional[Path] = None) -> Tuple[bool, str]:
    """(ok, why) for one course and language, cached by file identity."""
    base = Path(root) if root else library_dir()
    path = translation_path(source.course_id, lang, base)
    key = _file_key(path)
    cache_key = (str(base), source.course_id, lang)
    # The English the file was made from is part of the verdict: a changed source must not reuse an old "ok".
    ident = (key[0], key[1], source.sha)
    with _LOCK:
        hit = _CACHE.get(cache_key)
        if hit and hit[0] == (ident[0], ident[1], ident[2]):
            return hit[1], hit[2]
    if not path.is_file():
        verdict = (False, "missing")
    else:
        record = load_translation(source.course_id, lang, base)
        rows = [r for r in (record or {}).get("segments", []) if isinstance(r, dict)]
        if not record:
            verdict = (False, "unreadable")
        elif len(rows) != len(source.segments):
            verdict = (False, "segment_count")   # a file made before padding was removed, or a partial one
        else:
            verdict = v2.is_current(record, source, lang)
    with _LOCK:
        _CACHE[cache_key] = ((ident[0], ident[1], ident[2]), verdict[0], verdict[1])
    return verdict


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()


def _title_in(source: "v2.CourseSource", lang: str, root: Optional[Path]) -> str:
    record = load_translation(source.course_id, lang, Path(root) if root else None)
    return str((record or {}).get("title") or "").strip()


def _norm(text: str) -> str:
    return " ".join((text or "").casefold().replace("(audio)", " ").split())


def search(
    *,
    language: str = "en",
    q: str = "",
    include_english: bool = True,
    offset: int = 0,
    limit: int = 500,
    sources: Optional[Iterable["v2.CourseSource"]] = None,
    meta: Optional[Dict[str, Dict[str, Any]]] = None,
    root: Optional[Path] = None,
    languages: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Courses with the languages they are ready in, ranked ready-in-``language`` first.

    ``sources``/``meta``/``languages`` are injectable for tests; by default they come from the live audio catalog.
    """
    lang = language_family(language) or "en"
    base = Path(root) if root else None
    if sources is None:
        sources = v2.audio_sources()
    sources = list(sources)
    if meta is None:
        from .audio_courses import build_catalog

        meta = {
            c.id: {"category": c.category, "subject": c.subject, "level": c.level, "duration_min": c.duration_min,
                   "tags": list(c.tags), "segments": len(c.segments)}
            for c in build_catalog("en")
        }
    langs = [c for c in (languages if languages is not None else v2.translatable_languages()) if c != "en"]
    rows: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {c: 0 for c in langs}
    for src in sources:
        ready = [c for c in langs if shippable(src, c, base)[0]]
        for c in ready:
            counts[c] += 1
        m = meta.get(src.course_id, {})
        is_ready = lang == "en" or lang in ready
        title_local = _title_in(src, lang, base) if lang != "en" and lang in ready else ""
        rows.append({
            "id": src.course_id,
            "title": src.title,
            "title_local": title_local,
            "category": m.get("category") or src.category,
            "subject": m.get("subject", ""),
            "level": m.get("level", ""),
            "duration_min": m.get("duration_min", 0),
            "tags": m.get("tags", []),
            "segments": m.get("segments", len(src.segments)),
            "ready_languages": ready,
            "ready": is_ready,
            "english_only": not ready,
            "audio_mode": "live_tts",
        })
    if not include_english:
        rows = [r for r in rows if r["ready"]]
    needle = _norm(q)
    if needle:
        words = needle.split()
        rows = [r for r in rows if all(w in _norm(f"{r['title']} {r['title_local']} {r['category']} {r['subject']} {' '.join(r['tags'])}") for w in words)]
    rows.sort(key=lambda r: (0 if r["ready"] else 1, _norm(r["title_local"] or r["title"])))
    total = len(rows)
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 500))
    return {
        "language": lang,
        "total": total,
        "offset": offset,
        "limit": limit,
        "ready_in_language": sum(1 for r in rows if r["ready"]) if lang != "en" else total,
        "ready_counts": counts,
        "audio_mode": "live_tts",
        "courses": rows[offset: offset + limit],
    }
