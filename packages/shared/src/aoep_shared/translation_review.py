"""Employee review of machine-translated course text.

A review unit is one distinct English segment (heading + text), keyed by a hash,
so one review covers every course page that repeats that segment. The first
submission for a unit and language is final (HSETNX), so two employees never do
the same work. A short claim keeps two people from opening the same unit at once.

Storage is a small key-value client: Redis in production (shared by every
identity replica), :class:`MemoryKV` in tests and local runs.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .course_translation_library import library_dir, safe_course_id

VERDICTS = ("correct", "small_fix", "source_wrong", "better")
CLAIM_SECONDS = 600
_PREFIX = "aoep:tr:v1"


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def unit_key(heading: str, text: str) -> str:
    return hashlib.sha1(f"{_norm(heading)}|{_norm(text)}".encode()).hexdigest()[:16]


class MemoryKV:
    """The few Redis calls the store needs, in process."""

    def __init__(self) -> None:
        self._h: Dict[str, Dict[str, str]] = {}
        self._claims: Dict[str, Tuple[str, float]] = {}
        self._lock = threading.Lock()

    def hget(self, name: str, field: str) -> Optional[str]:
        return self._h.get(name, {}).get(field)

    def hsetnx(self, name: str, field: str, value: str) -> bool:
        with self._lock:
            bucket = self._h.setdefault(name, {})
            if field in bucket:
                return False
            bucket[field] = value
            return True

    def hgetall(self, name: str) -> Dict[str, str]:
        return dict(self._h.get(name, {}))

    def claim(self, name: str, owner: str, seconds: int) -> Optional[str]:
        """Take the claim, or return the current owner."""
        with self._lock:
            held = self._claims.get(name)
            if held and held[1] > time.time() and held[0] != owner:
                return held[0]
            self._claims[name] = (owner, time.time() + seconds)
            return None

    def claimed(self, name: str) -> Optional[str]:
        held = self._claims.get(name)
        return held[0] if held and held[1] > time.time() else None


class RedisKV:
    def __init__(self, client: Any) -> None:
        self._r = client

    @staticmethod
    def _s(value: Any) -> Optional[str]:
        if value is None:
            return None
        return value.decode() if isinstance(value, bytes) else str(value)

    def hget(self, name: str, field: str) -> Optional[str]:
        return self._s(self._r.hget(name, field))

    def hsetnx(self, name: str, field: str, value: str) -> bool:
        return bool(self._r.hsetnx(name, field, value))

    def hgetall(self, name: str) -> Dict[str, str]:
        return {self._s(k): self._s(v) for k, v in self._r.hgetall(name).items()}

    def claim(self, name: str, owner: str, seconds: int) -> Optional[str]:
        if self._r.set(name, owner, nx=True, ex=seconds):
            return None
        held = self._s(self._r.get(name))
        if held == owner:
            self._r.expire(name, seconds)
            return None
        return held

    def claimed(self, name: str) -> Optional[str]:
        return self._s(self._r.get(name))


# ---- Units from the catalog ---------------------------------------------------

@functools.lru_cache(maxsize=1)
def _catalog_units() -> Dict[str, Dict[str, Any]]:
    """key -> {heading, text, pages, courses[(id, index)...]} over audio courses."""
    from .audio_courses import build_catalog

    units: Dict[str, Dict[str, Any]] = {}
    for course in build_catalog("en", "en"):
        if course.id.startswith("lang-"):
            continue
        for index, seg in enumerate(course.segments):
            if not (seg.heading and seg.text):
                continue
            key = unit_key(seg.heading, seg.text)
            unit = units.setdefault(
                key, {"heading": seg.heading, "text": seg.text, "pages": 0, "titles": [], "where": []}
            )
            unit["pages"] += 1
            if len(unit["titles"]) < 4:
                unit["titles"].append(course.title.replace(" (audio)", "").strip())
            unit["where"].append((course.id, index))
    return units


def _library_record(course_id: str, lang: str) -> Optional[dict]:
    path = library_dir() / safe_course_id(course_id) / f"{lang}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@functools.lru_cache(maxsize=64)
def _machine_for_language(lang: str, signature: int) -> Dict[str, Dict[str, str]]:
    """key -> machine {heading, text} from the stored translation files."""
    out: Dict[str, Dict[str, str]] = {}
    seen_courses: Dict[str, Optional[dict]] = {}
    for key, unit in _catalog_units().items():
        for course_id, index in unit["where"]:
            if course_id not in seen_courses:
                seen_courses[course_id] = _library_record(course_id, lang)
            record = seen_courses[course_id]
            if not record:
                continue
            rows = record.get("segments") or []
            if index < len(rows):
                heading = str(rows[index].get("heading") or "").strip()
                text = str(rows[index].get("text") or "").strip()
                if heading and text:
                    out[key] = {"heading": heading, "text": text}
                    break
    return out


def _library_signature(lang: str) -> int:
    """Changes when translation files for ``lang`` are added or rewritten."""
    root = library_dir()
    total = 0
    try:
        for entry in root.iterdir():
            path = entry / f"{lang}.json"
            if path.is_file():
                total += int(path.stat().st_mtime)
    except OSError:
        return 0
    return total


def reviewable_languages() -> List[str]:
    root = library_dir()
    langs = set()
    try:
        for entry in root.iterdir():
            if entry.is_dir():
                langs.update(p.stem for p in entry.glob("*.json"))
    except OSError:
        pass
    return sorted(langs)


# ---- The store ------------------------------------------------------------------

class ReviewStore:
    def __init__(self, kv: Any = None) -> None:
        self.kv = kv or MemoryKV()

    @staticmethod
    def _hash(lang: str) -> str:
        return f"{_PREFIX}:{lang}"

    @staticmethod
    def _claim(lang: str, key: str) -> str:
        return f"{_PREFIX}:claim:{lang}:{key}"

    def _machine(self, lang: str) -> Dict[str, Dict[str, str]]:
        return _machine_for_language(lang, _library_signature(lang))

    def _reviews(self, lang: str) -> Dict[str, dict]:
        out: Dict[str, dict] = {}
        for key, raw in self.kv.hgetall(self._hash(lang)).items():
            try:
                out[key] = json.loads(raw)
            except ValueError:
                continue
        return out

    def next_unit(self, lang: str, reviewer: str, skip: Optional[List[str]] = None) -> Optional[dict]:
        """The most-reused unit nobody has reviewed or is reviewing."""
        units = _catalog_units()
        machine = self._machine(lang)
        done = self._reviews(lang)
        skipped = set(skip or [])
        ranked = sorted(
            (k for k in machine if k not in done and k not in skipped),
            key=lambda k: (-units[k]["pages"], k),
        )
        for key in ranked[:200]:
            if self.kv.claim(self._claim(lang, key), reviewer, CLAIM_SECONDS) is not None:
                continue
            unit = units[key]
            return {
                "key": key,
                "lang": lang,
                "source": {"heading": unit["heading"], "text": unit["text"]},
                "machine": machine[key],
                "pages": unit["pages"],
                "courses": unit["titles"],
                "claim_seconds": CLAIM_SECONDS,
            }
        return None

    def submit(
        self, lang: str, key: str, reviewer: str, verdict: str,
        heading: str = "", text: str = "", note: str = "",
    ) -> dict:
        """Record the review. Raises ValueError on bad input, LookupError if already reviewed."""
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
        machine = self._machine(lang).get(key)
        if key not in _catalog_units() or machine is None:
            raise ValueError("unknown review unit")
        text = " ".join((text or "").split())
        heading = " ".join((heading or "").split())
        if verdict in ("small_fix", "better") and not text:
            raise ValueError("type the corrected text")
        if verdict == "correct":
            final = dict(machine)
        elif verdict == "source_wrong":
            final = None
        else:
            final = {"heading": heading or machine["heading"], "text": text}
        record = {
            "verdict": verdict,
            "final": final,
            "reviewer": reviewer,
            "note": (note or "")[:500],
            "at": int(time.time()),
        }
        if not self.kv.hsetnx(self._hash(lang), key, json.dumps(record, ensure_ascii=False)):
            existing = json.loads(self.kv.hget(self._hash(lang), key) or "{}")
            raise LookupError(existing.get("reviewer", "another reviewer"))
        return record

    def stats(self, lang: str) -> dict:
        units = _catalog_units()
        machine = self._machine(lang)
        reviews = {k: v for k, v in self._reviews(lang).items() if k in machine}
        by_verdict = {v: 0 for v in VERDICTS}
        by_reviewer: Dict[str, int] = {}
        for rec in reviews.values():
            by_verdict[rec.get("verdict", "")] = by_verdict.get(rec.get("verdict", ""), 0) + 1
            name = rec.get("reviewer", "")
            by_reviewer[name] = by_reviewer.get(name, 0) + 1
        total_pages = sum(units[k]["pages"] for k in machine)
        done_pages = sum(units[k]["pages"] for k in reviews)
        return {
            "lang": lang,
            "units_total": len(machine),
            "units_reviewed": len(reviews),
            "units_remaining": len(machine) - len(reviews),
            "pages_total": total_pages,
            "pages_covered": done_pages,
            "by_verdict": by_verdict,
            "by_reviewer": dict(sorted(by_reviewer.items(), key=lambda kv: -kv[1])),
            "untranslated_units": len(units) - len(machine),
        }

    def gold_pairs(self, lang: str) -> List[dict]:
        """Reviewed (source, target) pairs, ready for training data."""
        units = _catalog_units()
        rows = []
        for key, rec in self._reviews(lang).items():
            final = rec.get("final")
            if key in units and final:
                rows.append({
                    "key": key, "lang": lang,
                    "source": {"heading": units[key]["heading"], "text": units[key]["text"]},
                    "target": final, "verdict": rec["verdict"], "reviewer": rec["reviewer"],
                })
        return rows
