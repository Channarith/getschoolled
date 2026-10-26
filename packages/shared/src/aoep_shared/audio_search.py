"""Search index for the audio ("On the Go") courses: which courses have a SHIPPABLE translation in which language.

A language is listed for a course only when the library file is the right shape (same segments as today's English), is a
translation of today's English (provenance source hash) and still passes the v2 validator (``translation_v2.is_current``).
Held, rejected, stale, wrongly filed or partial files are never listed, so the picker never offers a course it would read in the
wrong language. The verdicts are cached per file (path, mtime, size), so a search is cheap and a newly written file shows up on the
next request.

Narration is live text-to-speech in the voice the learner picked: ``audio_mode`` says so (there are no per-course pre-rendered clips).
"""
from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
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


def fold(text: str) -> str:
    """Lowercase, accent-free, punctuation-free; keeps the letters and numbers of every script (same rule as the web search)."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.category(ch).startswith("M")).casefold().replace("(audio)", " ")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE).replace("_", " ")
    return " ".join(t.split())


_ALIASES: Optional[List[List[str]]] = None


def aliases() -> List[List[str]]:
    """Groups of equivalent search terms (data/course_search_aliases.json): one source for the server and the web client."""
    global _ALIASES
    if _ALIASES is None:
        try:
            raw = json.loads((Path(__file__).parent / "data" / "course_search_aliases.json").read_text(encoding="utf-8"))
            _ALIASES = [[fold(t) for t in g if fold(t)] for g in raw.get("groups", []) if isinstance(g, list)]
        except (OSError, ValueError):
            _ALIASES = []
    return _ALIASES


def alias_terms(query: str, groups: Optional[List[List[str]]] = None) -> List[str]:
    """Other terms to look for when ``query`` equals, or starts, a term of an alias group ("cp" -> "cpr" -> "first aid")."""
    q = fold(query)
    if len(q) < 2:
        return []
    out: List[str] = []
    for group in (groups if groups is not None else aliases()):
        if any(t == q or t.startswith(q) for t in group):
            out.extend(t for t in group if t not in out)
    return out


def _words(text: str) -> List[str]:
    return fold(text).split()


def _unspaced(text: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\u0e00-\u0e7f\u1780-\u17ff]", text or ""))


def match_rank(query: str, title: str, other: str = "", extra_aliases: Optional[List[List[str]]] = None) -> Optional[int]:
    """None when the course does not match; else a rank, lower is better.

    0 every query word starts a title word; 1 every word is inside the title; 2 matches in subject/category/tags;
    3 found through an alias group ("cp" -> "cpr" -> First Aid and CPR, "machine vision" -> Computer Vision).
    """
    q = fold(query)
    if not q:
        return 0
    t, o = fold(title), fold(other)
    if _unspaced(q):
        return 1 if q.replace(" ", "") in t.replace(" ", "") else (2 if q.replace(" ", "") in o.replace(" ", "") else None)
    qw = q.split()
    tw, ow = t.split(), o.split()
    if all(any(w.startswith(x) for w in tw) for x in qw):
        return 0
    inside = all(len(x) >= 3 for x in qw)   # a 2-letter query may start a word but not hide inside one ("ai" in "explained")
    if inside and all(x in t for x in qw):
        return 1
    if all(any(w.startswith(x) for w in tw + ow) or (inside and (x in t or x in o)) for x in qw):
        return 2
    for alt in alias_terms(q, extra_aliases):
        if alt == q:
            continue
        if _alt_in(alt, t, tw) or _alt_in(alt, o, ow):
            return 3
    return None


def _alt_in(alt: str, text: str, words: List[str]) -> bool:
    """A short term ("ai", "ml") must be a whole word, so it does not match inside "training"; longer ones may sit inside a word."""
    return alt in words if len(alt) < 4 else alt in text


_STOP = {"to", "a", "an", "the", "of", "and", "for", "in", "on", "with"}


def _dedupe_key(title: str) -> str:
    """Titles that differ only by 'Intro'/'Introduction' or small words are the same topic."""
    words = [("intro" if w == "introduction" else w) for w in fold(title).split() if w not in _STOP]
    return " ".join(words)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-") or "topic"


_PLANNED: Optional[List[Dict[str, str]]] = None


def planned_topics(built_titles: Iterable[str]) -> List[Dict[str, str]]:
    """Topics the catalog defines but has no course for yet ("First Aid and CPR"): searchable, shown as coming soon."""
    global _PLANNED
    if _PLANNED is None:
        from .audio_courses import _TOPICS

        _PLANNED = [{"id": f"planned-{_slug(t)}", "title": t, "category": cat} for cat, ts in _TOPICS.items() for t in ts]
    have = {_dedupe_key(t) for t in built_titles}
    return [p for p in _PLANNED if _dedupe_key(p["title"]) not in have]


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
    include_planned: bool = False,
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
            c.id: {"title": c.title.replace(" (audio)", "").strip(), "category": c.category, "subject": c.subject, "level": c.level, "duration_min": c.duration_min,
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
    # Catalog courses the translation pipeline does not cover (the language lessons) are still courses: list them, English only.
    listed = {r["id"] for r in rows}
    for cid, m in meta.items():
        if cid in listed:
            continue
        rows.append({
            "id": cid, "title": m.get("title") or cid, "title_local": "", "category": m.get("category", ""), "subject": m.get("subject", ""),
            "level": m.get("level", ""), "duration_min": m.get("duration_min", 0), "tags": m.get("tags", []), "segments": m.get("segments", 0),
            "ready_languages": [], "ready": lang == "en", "english_only": True, "audio_mode": "live_tts", "audio": True, "kind": "language",
        })
    for r in rows:
        r.setdefault("audio", True)
    catalog_titles = [r["title"] for r in rows]
    if not include_english:
        rows = [r for r in rows if r["ready"]]
    needle = fold(q)
    ranks: Dict[str, int] = {}
    if needle:
        kept = []
        for r in rows:
            rank = match_rank(needle, f"{r['title']} {r['title_local']}", f"{r['category']} {r['subject']} {' '.join(r['tags'])}")
            if rank is not None:
                ranks[r["id"]] = rank
                kept.append(r)
        rows = kept
    rows.sort(key=lambda r: (0 if r["ready"] else 1, ranks.get(r["id"], 0), _norm(r["title_local"] or r["title"])))
    total = len(rows)
    offset = max(0, int(offset))
    limit = max(1, min(int(limit), 500))
    planned: List[Dict[str, Any]] = []
    if include_planned:
        for pt in planned_topics(catalog_titles):
            rank = match_rank(needle, pt["title"], pt["category"]) if needle else 0
            if rank is not None:
                planned.append({**pt, "subject": pt["category"], "ready_languages": [], "ready": False, "english_only": True,
                                "audio": False, "planned": True, "rank": rank})
        planned.sort(key=lambda r: (r["rank"], _norm(r["title"])))
    return {
        "language": lang,
        "total": total,
        "offset": offset,
        "limit": limit,
        "ready_in_language": sum(1 for r in rows if r["ready"]) if lang != "en" else total,
        "ready_counts": counts,
        "audio_mode": "live_tts",
        "courses": rows[offset: offset + limit],
        "planned": planned,
        "aliases": aliases(),
    }
