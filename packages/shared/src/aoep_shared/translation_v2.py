"""Course translation pipeline v2: output that can ship, and proof of what it was made from.

What v1 got wrong (found when the iBuyPower library was validated):
  * Files were reused by name or by segment count, so translations made from the old padded
    English kept being "skipped" after the English changed.
  * NLLB loops, leaves Latin text in place and drops numbers; nothing re-tried those segments.
  * A domain word could come out in the wrong sense ("fractions" became Khmer "shares").

v2 in short:
  * Every file records ``provenance`` (sha256 of the English it came from, engine, model,
    generation settings, pipeline version). A file is reused only when that matches AND the
    validator still says "ship".
  * Segments are masked (URLs, section titles, glossary terms, optionally numbers), translated
    in length-sorted batches, then checked with the same rules the validator uses. A segment
    that fails is retried on a ladder of stricter settings. A segment that still fails is
    never written to the library: it goes to a work file for the opt-in Grok fallback or a person.
  * ``data/translation_glossary.json`` pins approved words for domain terms. Entries are
    "unreviewed" until a native speaker confirms them.

The engine is pluggable (``translate(texts, source, target, gen) -> list[str]``) so tests need no GPU.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from .course_translation_library import (
    EXTRA_TRANSLATION_LANGUAGES,
    TARGET_LANGUAGES,
    library_dir,
    load_translation,
    safe_course_id,
    save_translation,
)
from .translation_validate import (
    SHIP,
    _seg_findings,
    has_loop,
    judge_record,
    script_fraction,
)

PIPELINE_VERSION = "2.0"
PIPELINE_MAJOR = PIPELINE_VERSION.split(".")[0]

# One ordered queue for every machine. Why this order:
#   1. the owner's six first: Khmer (the product), Cantonese, Spanish, Mandarin, French, Italian;
#   2. Thai and Vietnamese (demo languages);
#   3. the big, well-supported languages (population and web presence times NLLB-200 quality):
#      Japanese, Korean, Portuguese, German, Russian, Arabic, Hindi, Indonesian, Turkish;
#   4. the remaining platform languages, then Tagalog/Filipino (translation-only extra) last.
# yue and tl are not platform languages: they are written to <language>.json by the translation library only.
PRIORITY_ORDER = (
    "km", "yue", "es", "zh", "fr", "it",
    "th", "vi",
    "ja", "ko", "pt", "de", "ru", "ar", "hi", "id", "tr",
    "pl", "nl", "uk", "he", "bn", "fa", "ur", "el", "cs", "sw",
    "tl",
)
# --tier N is a prefix of PRIORITY_ORDER: TIER1 = the six + th + vi, TIER1 + TIER2 = through tr, tier 3 = all.
TIER1 = PRIORITY_ORDER[:8]
TIER2 = PRIORITY_ORDER[8:17]


def translatable_languages() -> List[str]:
    return list(TARGET_LANGUAGES) + [c for c in EXTRA_TRANSLATION_LANGUAGES if c not in TARGET_LANGUAGES]


def priority_languages() -> List[str]:
    valid = set(translatable_languages())
    ordered = [c for c in PRIORITY_ORDER if c in valid]
    ordered += [c for c in translatable_languages() if c not in ordered]  # a language added later still gets translated
    return ordered


# ---------------------------------------------------------------------------
# source identity
# ---------------------------------------------------------------------------

def _clean_segments(segments: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    out = []
    for row in segments:
        heading = str(row.get("heading") or "").strip()
        text = str(row.get("text") or "").strip()
        if heading and text:
            out.append({"heading": heading, "text": text, "kind": str(row.get("kind") or "narration")})
    return out


def source_sha256(title: str, segments: Iterable[Dict[str, Any]]) -> str:
    """Stable hash of the English a translation is made from (title + non-empty segments)."""
    rows = _clean_segments(segments)
    payload = json.dumps(
        {"title": (title or "").strip(), "segments": [[r["heading"], r["text"]] for r in rows]},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class CourseSource:
    course_id: str
    title: str
    category: str
    segments: List[Dict[str, str]]

    def __post_init__(self) -> None:
        self.segments = _clean_segments(self.segments)

    @property
    def sha(self) -> str:
        return source_sha256(self.title, self.segments)


def audio_sources() -> List[CourseSource]:
    """The current English of the audio catalog (what learners hear today)."""
    from .audio_courses import build_catalog

    return [
        CourseSource(
            c.id,
            c.title.replace(" (audio)", "").strip(),
            c.category,
            [{"heading": s.heading, "text": s.text, "kind": s.kind} for s in c.segments],
        )
        for c in build_catalog("en", "en")
        if not c.id.startswith("lang-")
    ]


def studio_sources() -> List[CourseSource]:
    """Course Studio narration (optional package); empty when it is not importable."""
    try:
        from theodore_course_studio.narration_catalog import enumerate_courses
    except Exception:  # noqa: BLE001
        return []
    out: List[CourseSource] = []
    for course in enumerate_courses():
        segs = []
        for slide in course.slides:
            text = (slide.narration or slide.body or "").strip()
            heading = (slide.title or "").strip()
            if heading and text:
                segs.append({"heading": heading, "text": text, "kind": "narration"})
        if segs:
            out.append(CourseSource(course.course_id, course.title, course.course_kind, segs))
    return out


# ---------------------------------------------------------------------------
# glossary
# ---------------------------------------------------------------------------

_GLOSSARY_PATH = Path(__file__).resolve().parents[4] / "data" / "translation_glossary.json"


class Glossary:
    """Approved words for domain terms. Every entry is unreviewed until a native speaker confirms it."""

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        data = data or {}
        self.version = int(data.get("version") or 0)
        self.keep: List[str] = [str(k) for k in data.get("keep") or []]
        self.terms: List[Dict[str, Any]] = list(data.get("terms") or [])

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Glossary":
        candidate = Path(path) if path else Path(os.environ.get("AOEP_TRANSLATION_GLOSSARY") or _GLOSSARY_PATH)
        try:
            return cls(json.loads(candidate.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls({})

    def _applies(self, term: Dict[str, Any], text: str, category: str) -> bool:
        ctx = [str(w).lower() for w in term.get("context_words") or []]
        if ctx and not any(w in text.lower() for w in ctx):
            return False
        cats = [str(c).lower() for c in term.get("categories") or []]
        if cats and not any(c in (category or "").lower() for c in cats):
            return False
        return True

    def entries_for(self, text: str, lang: str, category: str = "") -> List[Tuple[re.Pattern, str, str, Dict[str, Any]]]:
        """[(pattern, target text, term id, target entry)] for terms that occur in ``text`` and have a target in ``lang``."""
        found = []
        for term in self.terms:
            target = (term.get("targets") or {}).get(lang)
            if not target or not target.get("text"):
                continue
            if not self._applies(term, text, category):
                continue
            forms = [str(f) for f in term.get("en") or []]
            for form in sorted(forms, key=len, reverse=True):
                pattern = re.compile(r"\b" + re.escape(form) + r"\b", re.IGNORECASE)
                if pattern.search(text):
                    plural = bool(target.get("plural")) and form.lower() != forms[0].lower()
                    found.append((pattern, target["plural"] if plural else target["text"], str(term.get("id")), target))
        return found

    def avoid_hits(self, text: str, lang: str) -> List[str]:
        hits = []
        for term in self.terms:
            target = (term.get("targets") or {}).get(lang) or {}
            for bad in target.get("avoid") or []:
                if bad and bad in text:
                    hits.append(f"{term.get('id')}: {bad}")
        return hits

    def review_items(self) -> List[Dict[str, str]]:
        """Rows the staff review lab can import as 'please confirm this word' items."""
        rows = []
        for term in self.terms:
            for lang, target in (term.get("targets") or {}).items():
                rows.append(
                    {
                        "term": str(term.get("id")),
                        "en": ", ".join(term.get("en") or []),
                        "language": lang,
                        "proposed": str(target.get("text") or ""),
                        "avoid": ", ".join(target.get("avoid") or []),
                        "status": str(target.get("status") or "unreviewed"),
                    }
                )
        return rows


# ---------------------------------------------------------------------------
# masking and chunking
# ---------------------------------------------------------------------------

_PLACEHOLDER = re.compile(r"\[\[\s*(\d+)\s*\]\]")
_URL = re.compile(r"https?://[^\s)>\]]+")
_NUMBER_OR_PH = re.compile(r"(\[\[\s*\d+\s*\]\])|(\d+(?:[.,]\d+)?)")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class Masker:
    """Swap fragile text for ``[[n]]`` markers before translation and put it back afterwards."""

    def __init__(self) -> None:
        self.restores: List[str] = []
        self.terms: List[str] = []

    def add(self, restore: str) -> str:
        self.restores.append(restore)
        return f"[[{len(self.restores) - 1}]]"

    def restore(self, text: str) -> Tuple[str, int]:
        """Return (text with markers replaced, number of markers that did not survive translation)."""
        seen = set()

        def put(match: re.Match) -> str:
            i = int(match.group(1))
            if i < len(self.restores):
                seen.add(i)
                return self.restores[i]
            return match.group(0)

        out = _PLACEHOLDER.sub(put, text)
        # A marker the model invented or damaged ([[9]] with no source) also counts as lost.
        stray = len(_PLACEHOLDER.findall(out))
        return out, (len(self.restores) - len(seen)) + stray


def mask_text(
    text: str,
    *,
    masker: Masker,
    lang: str,
    category: str,
    glossary: Glossary,
    heading_map: Dict[str, str],
    mask_numbers: bool,
) -> str:
    out = _URL.sub(lambda m: masker.add(m.group(0)), text)
    if mask_numbers:
        out = _NUMBER_OR_PH.sub(lambda m: m.group(1) or masker.add(m.group(2).replace(",", ".")), out)
    for word in glossary.keep:
        out = re.sub(r"\b" + re.escape(word) + r"\b", lambda m: masker.add(m.group(0)), out)
    # Section titles and the course title mentioned inside a passage: translate them once (as
    # headings) and drop the same translation in, so the passage never carries Latin leftovers.
    for source in sorted(heading_map, key=len, reverse=True):
        if len(source) >= 4 and heading_map[source]:
            out = re.sub(
                r"(?<![\w\[])" + re.escape(source) + r"(?![\w\]])",
                lambda m, t=heading_map[source]: masker.add(t),
                out,
            )
    for pattern, target_text, term_id, _entry in glossary.entries_for(out, lang, category):
        before = len(masker.restores)
        out = pattern.sub(lambda m, t=target_text: masker.add(t), out)
        if len(masker.restores) > before:
            masker.terms.append(term_id)
    return out


def split_sentences(text: str) -> List[str]:
    return [s for s in _SENTENCE.split(" ".join((text or "").split())) if s.strip()]


def chunk_text(text: str, max_words: int = 40, per_sentence: bool = False) -> List[str]:
    """Sentence-aligned chunks. NLLB translates sentences best, so long text is never sent whole."""
    sentences = split_sentences(text)
    pieces: List[str] = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) > 60:  # a very long sentence: split on words, never inside a [[marker]]
            for start in range(0, len(words), 40):
                pieces.append(" ".join(words[start : start + 40]))
        else:
            pieces.append(sentence)
    if per_sentence:
        return pieces
    chunks: List[str] = []
    current: List[str] = []
    count = 0
    for piece in pieces:
        n = len(piece.split())
        if current and count + n > max_words:
            chunks.append(" ".join(current))
            current, count = [piece], n
        else:
            current.append(piece)
            count += n
    if current:
        chunks.append(" ".join(current))
    return chunks


def join_chunks(parts: List[str], lang: str) -> str:
    joiner = "" if lang in {"zh", "ja"} else " "
    return joiner.join(p.strip() for p in parts if p and p.strip()).strip()


# ---------------------------------------------------------------------------
# engine and the retry ladder
# ---------------------------------------------------------------------------

class Engine(Protocol):
    name: str
    model: str

    def translate(self, texts: List[str], source: str, target: str, gen: Dict[str, Any]) -> List[str]: ...


class NllbEngine:
    """Local NLLB-200 (GPU on the Spark, required there by aoep_shared.devices)."""

    name = "nllb"

    def __init__(self, batch_size: Optional[int] = None) -> None:
        self.model = os.environ.get("NLLB_MODEL") or "facebook/nllb-200-distilled-600M"
        self.batch_size = batch_size

    def translate(self, texts: List[str], source: str, target: str, gen: Dict[str, Any]) -> List[str]:
        from . import nllb

        return nllb.translate_batch(texts, source=source, target=target, batch_size=self.batch_size, gen=gen)


@dataclass(frozen=True)
class Rung:
    name: str
    masked: bool
    mask_numbers: bool
    chunk_words: int
    per_sentence: bool
    gen: Dict[str, Any] = field(default_factory=dict, hash=False, compare=False)


RUNGS: Tuple[Rung, ...] = (
    Rung("r0", True, False, 40, False, {"num_beams": 4, "no_repeat_ngram_size": 4, "repetition_penalty": 1.1, "max_len_ratio": 3.0}),
    Rung("r1", True, False, 40, False, {"num_beams": 5, "no_repeat_ngram_size": 3, "repetition_penalty": 1.2, "length_penalty": 1.0, "max_len_ratio": 2.6}),
    Rung("r2", True, True, 20, True, {"num_beams": 6, "no_repeat_ngram_size": 3, "repetition_penalty": 1.3, "max_len_ratio": 2.4}),
    Rung("r3", True, True, 20, True, {"num_beams": 1, "do_sample": True, "temperature": 0.6, "top_p": 0.9, "repetition_penalty": 1.2, "seed": 11, "max_len_ratio": 2.4}),
    Rung("r4", False, False, 20, True, {"num_beams": 1, "do_sample": True, "temperature": 0.8, "top_p": 0.95, "repetition_penalty": 1.25, "seed": 23, "max_len_ratio": 2.4}),
)

# Findings that make a segment unusable. (Anything else the validator reports is a hold, not a failure.)
FAILING = {
    "empty", "degenerate_loop", "wrong_script", "length_outlier", "number_mismatch",
    "unchanged_from_english", "leftover_markup", "url_mismatch", "placeholder_lost", "glossary_avoid",
}


# ---------------------------------------------------------------------------
# per-course work state (resumable) and results
# ---------------------------------------------------------------------------

def work_dir(root: Path) -> Path:
    return Path(root) / "_work"


def work_path(root: Path, course_id: str, lang: str) -> Path:
    return work_dir(root) / safe_course_id(course_id) / f"{lang}.json"


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


@dataclass
class CourseResult:
    course_id: str
    language: str
    status: str  # written | reused | needs_fallback | failed
    retried: int = 0
    fallback: int = 0
    rungs: Dict[str, int] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _heading_ok(lang: str, translated: str, source: str) -> bool:
    if not translated.strip() or has_loop(translated):
        return False
    frac = script_fraction(translated, lang)
    if frac is not None and frac < 0.5:
        return False
    ratio = len(translated) / max(1, len(source))
    return 0.15 <= ratio <= 5.0


def segment_findings(lang: str, heading: str, text: str, src: Dict[str, str], glossary: Glossary) -> List[str]:
    found = [f for f in _seg_findings(lang, heading, text, src, False) if f in FAILING]
    if glossary.avoid_hits(f"{heading} {text}", lang):
        found.append("glossary_avoid")
    return found


def is_current(record: Optional[dict], source: CourseSource, lang: str, *, accept_backfilled: bool = True) -> Tuple[bool, str]:
    """Is an existing file still the right translation of today's English? (reason when not)"""
    if not record:
        return False, "missing"
    prov = record.get("provenance")
    if not isinstance(prov, dict):
        return False, "no_provenance"
    if str(prov.get("pipeline") or "").split(".")[0] not in {PIPELINE_MAJOR, "backfill-1"}:
        return False, "pipeline_changed"
    if prov.get("source_sha256") != source.sha:
        return False, "source_changed"
    if prov.get("backfilled") and not accept_backfilled:
        return False, "backfilled"
    verdict = judge_record(record, lang, source.segments, course_id=source.course_id)
    if verdict["verdict"] != SHIP:
        return False, "fails_validator: " + "; ".join(verdict["reasons"][:2])
    return True, "current"


def check_library(
    sources: Iterable[CourseSource], languages: Iterable[str], root: Optional[Path] = None, *, accept_backfilled: bool = True
) -> Dict[str, Any]:
    """List what is current and what is stale, without translating anything."""
    root = Path(root) if root else library_dir()
    counts: Dict[str, int] = {}
    stale: List[Dict[str, str]] = []
    for source in sources:
        for lang in languages:
            ok, why = is_current(load_translation(source.course_id, lang, root), source, lang, accept_backfilled=accept_backfilled)
            key = "current" if ok else why.split(":")[0]
            counts[key] = counts.get(key, 0) + 1
            if not ok:
                stale.append({"course_id": source.course_id, "language": lang, "why": why})
    return {"root": str(root), "counts": counts, "stale": stale}


def translate_course(
    source: CourseSource,
    lang: str,
    engine: Engine,
    *,
    glossary: Optional[Glossary] = None,
    root: Optional[Path] = None,
    max_rungs: int = len(RUNGS),
    force: bool = False,
    accept_backfilled: bool = True,
) -> CourseResult:
    """Translate one course into one language, or say precisely why it could not be done."""
    root = Path(root) if root else library_dir()
    glossary = glossary if glossary is not None else Glossary.load()
    result = CourseResult(source.course_id, lang, "failed")
    if not force:
        ok, _why = is_current(load_translation(source.course_id, lang, root), source, lang, accept_backfilled=accept_backfilled)
        if ok:
            result.status = "reused"
            return result

    state_file = work_path(root, source.course_id, lang)
    state = _read_json(state_file) or {}
    if state.get("source_sha256") != source.sha or str(state.get("pipeline", "")).split(".")[0] != PIPELINE_MAJOR:
        state = {"source_sha256": source.sha, "pipeline": PIPELINE_VERSION, "segments": {}, "headings": {}}

    # 1. titles and section headings (short; also reused inside passages)
    heading_sources = [source.title] + [s["heading"] for s in source.segments]
    todo = [h for h in dict.fromkeys(heading_sources) if h not in state["headings"]]
    if todo:
        first = engine.translate(todo, "en", lang, dict(RUNGS[0].gen))
        retry = [h for h, t in zip(todo, first) if not _heading_ok(lang, t, h)]
        second = dict(zip(retry, engine.translate(retry, "en", lang, dict(RUNGS[2].gen)))) if retry else {}
        for h, t in zip(todo, first):
            t2 = second.get(h, t)
            if _heading_ok(lang, t2, h):
                state["headings"][h] = t2.strip()
    missing_heads = [h for h in heading_sources if h not in state["headings"]]
    if missing_heads:
        _write_json(state_file, state)
        result.status = "needs_fallback"
        result.fallback = len(missing_heads)
        result.reasons = [f"heading could not be translated cleanly: {h[:60]}" for h in missing_heads[:3]]
        return result
    heading_map = {h: state["headings"][h] for h in dict.fromkeys(heading_sources)}

    # 2. passages, on the ladder
    segs = state["segments"]
    best: Dict[int, Dict[str, Any]] = {}
    tried: Dict[int, int] = {}
    for rung in RUNGS[: max(1, max_rungs)]:
        pending = [i for i in range(len(source.segments)) if not (segs.get(str(i)) or {}).get("ok")]
        if not pending:
            break
        plans: Dict[int, Tuple[Masker, List[str]]] = {}
        flat: List[str] = []
        for i in pending:
            seg = source.segments[i]
            masker = Masker()
            masked = (
                mask_text(seg["text"], masker=masker, lang=lang, category=source.category, glossary=glossary,
                          heading_map=heading_map, mask_numbers=rung.mask_numbers)
                if rung.masked else seg["text"]
            )
            parts = chunk_text(masked, rung.chunk_words, rung.per_sentence)
            plans[i] = (masker, parts)
            flat.extend(parts)
        outputs = engine.translate(flat, "en", lang, dict(rung.gen)) if flat else []
        cursor = 0
        for i in pending:
            masker, parts = plans[i]
            pieces = outputs[cursor : cursor + len(parts)]
            cursor += len(parts)
            text, lost = masker.restore(join_chunks(pieces, lang))
            tried[i] = tried.get(i, 0) + 1
            seg = source.segments[i]
            findings = segment_findings(lang, heading_map[seg["heading"]], text, {"heading": seg["heading"], "text": seg["text"]}, glossary)
            if lost:
                findings.append("placeholder_lost")
            entry = {"i": i, "heading": heading_map[seg["heading"]], "text": text, "ok": not findings, "findings": findings, "rung": rung.name, "terms": sorted(set(plans[i][0].terms))}
            if entry["ok"]:
                segs[str(i)] = entry
                result.rungs[rung.name] = result.rungs.get(rung.name, 0) + 1
            elif i not in best or len(findings) < len(best[i]["findings"]):
                best[i] = entry
    result.retried = sum(1 for i, n in tried.items() if n > 1 and (segs.get(str(i)) or {}).get("ok"))

    failing = [i for i in range(len(source.segments)) if not (segs.get(str(i)) or {}).get("ok")]
    for i in failing:
        if i in best:
            segs[str(i)] = best[i]
    state["updated_at"] = _now()
    if failing:
        _write_json(state_file, state)
        result.status = "needs_fallback"
        result.fallback = len(failing)
        result.reasons = [f"segment {i + 1}: {', '.join(segs[str(i)].get('findings', []))}" for i in failing[:5] if str(i) in segs]
        return result
    return _finalize(source, lang, state, engine, glossary, root, result)


def _finalize(
    source: CourseSource, lang: str, state: dict, engine: Engine, glossary: Glossary, root: Path, result: CourseResult,
    *, engine_name: Optional[str] = None,
) -> CourseResult:
    segments = []
    used_terms: set = set()
    for i, seg in enumerate(source.segments):
        row = state["segments"][str(i)]
        segments.append({"heading": row["heading"], "text": row["text"], "kind": seg.get("kind", "narration")})
        used_terms.update(row.get("terms") or [])
    title = state["headings"].get(source.title, "")
    record = {
        "course_id": source.course_id,
        "title": title or source.title,
        "category": source.category,
        "language": lang,
        "source": "batch-v2",
        "segments": segments,
        "provenance": {
            "pipeline": PIPELINE_VERSION,
            "source_sha256": source.sha,
            "engine": engine_name or engine.name,
            "model": getattr(engine, "model", ""),
            "rungs_used": result.rungs,
            "generated_at": _now(),
            "glossary_version": glossary.version,
            "glossary_terms_applied": sorted(used_terms),
            "glossary_unreviewed": bool(used_terms),
            "backfilled": False,
        },
    }
    verdict = judge_record(record, lang, source.segments, course_id=source.course_id)
    if verdict["verdict"] != SHIP:
        _write_json(work_path(root, source.course_id, lang), state)
        result.status = "needs_fallback"
        result.reasons = ["whole file fails the validator: " + "; ".join(verdict["reasons"][:3])]
        return result
    save_translation(record, root)
    partial = work_path(root, source.course_id, lang)
    if partial.is_file():
        partial.unlink()
    result.status = "written"
    return result


# ---------------------------------------------------------------------------
# Grok fallback (opt in, capped)
# ---------------------------------------------------------------------------

def fallback_work(root: Path, languages: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Segments still failing after the ladder: course, language, index, English, best attempt, findings."""
    items: List[Dict[str, Any]] = []
    wd = work_dir(root)
    if not wd.is_dir():
        return items
    wanted = set(languages) if languages else None
    for course_dir in sorted(p for p in wd.iterdir() if p.is_dir()):
        for f in sorted(course_dir.glob("*.json")):
            lang = f.stem
            if wanted and lang not in wanted:
                continue
            state = _read_json(f) or {}
            for key, row in (state.get("segments") or {}).items():
                if not row.get("ok"):
                    items.append({"course_id": course_dir.name, "language": lang, "index": int(key), "best": row.get("text", ""), "findings": row.get("findings", [])})
    return items


def estimate_fallback(items: List[Dict[str, Any]], sources: Dict[str, CourseSource], price_per_mtok: Optional[float] = None) -> Dict[str, Any]:
    words = 0
    for item in items:
        src = sources.get(item["course_id"])
        if src and item["index"] < len(src.segments):
            words += len(src.segments[item["index"]]["text"].split())
    tokens = int(words * 1.4)  # English words -> tokens, input
    out_tokens = int(tokens * 2.2)  # target-language output is longer in tokens (Khmer, Thai especially)
    est = {"segments": len(items), "source_words": words, "est_input_tokens": tokens, "est_output_tokens": out_tokens}
    if price_per_mtok is not None:
        est["est_cost_usd"] = round((tokens + out_tokens) / 1_000_000 * price_per_mtok, 4)
    return est


def run_fallback(
    root: Path,
    sources: Dict[str, CourseSource],
    languages: Iterable[str],
    translate_one: Callable[[str, str, str], str],
    *,
    glossary: Optional[Glossary] = None,
    enabled: bool = False,
    cap_segments: int = 50,
) -> Dict[str, int]:
    """Fill failing segments from a paid API. OFF unless ``enabled``; stops at ``cap_segments``.

    A course is written only when every segment now passes. The API output goes through the same
    checks as NLLB output: a fallback translation is not trusted because it came from a bigger model.
    """
    stats = {"attempted": 0, "fixed": 0, "files_written": 0, "still_failing": 0}
    if not enabled:
        return stats
    glossary = glossary if glossary is not None else Glossary.load()
    items = fallback_work(root, languages)
    by_file: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for item in items:
        by_file.setdefault((item["course_id"], item["language"]), []).append(item)
    for (course_id, lang), group in by_file.items():
        source = sources.get(course_id)
        state = _read_json(work_path(root, course_id, lang))
        if not source or not state or state.get("source_sha256") != source.sha:
            continue
        for item in group:
            if stats["attempted"] >= cap_segments:
                break
            seg = source.segments[item["index"]]
            stats["attempted"] += 1
            text = (translate_one(seg["text"], "en", lang) or "").strip()
            heading = state["headings"].get(seg["heading"], "")
            if text and not segment_findings(lang, heading, text, seg, glossary):
                state["segments"][str(item["index"])] = {"i": item["index"], "heading": heading, "text": text, "ok": True, "findings": [], "rung": "fallback", "terms": []}
                stats["fixed"] += 1
            else:
                stats["still_failing"] += 1
        _write_json(work_path(root, course_id, lang), state)
        if all((state["segments"].get(str(i)) or {}).get("ok") for i in range(len(source.segments))):
            res = _finalize(source, lang, state, _FallbackEngine(), glossary, Path(root), CourseResult(course_id, lang, "failed", rungs={"fallback": len(group)}), engine_name="grok-fallback")
            if res.status == "written":
                stats["files_written"] += 1
    return stats


class _FallbackEngine:
    name = "grok-fallback"
    model = "xai"

    def translate(self, texts, source, target, gen):  # pragma: no cover - never called
        raise NotImplementedError


# ---------------------------------------------------------------------------
# catalog runner
# ---------------------------------------------------------------------------

def run_catalog(
    sources: List[CourseSource],
    languages: List[str],
    engine: Engine,
    *,
    root: Optional[Path] = None,
    glossary: Optional[Glossary] = None,
    max_rungs: int = len(RUNGS),
    force: bool = False,
    accept_backfilled: bool = True,
    progress: Optional[Callable[[CourseResult, int, int], None]] = None,
) -> Dict[str, Any]:
    """Languages in priority order, every course, resumable. Returns per-run statistics."""
    root = Path(root) if root else library_dir()
    glossary = glossary if glossary is not None else Glossary.load()
    stats = {"written": 0, "reused": 0, "needs_fallback": 0, "failed": 0, "retried_segments": 0, "fallback_segments": 0, "rungs": {}}
    total = len(sources) * len(languages)
    done = 0
    for lang in languages:
        for source in sources:
            res = translate_course(source, lang, engine, glossary=glossary, root=root, max_rungs=max_rungs, force=force, accept_backfilled=accept_backfilled)
            done += 1
            stats[res.status] = stats.get(res.status, 0) + 1
            stats["retried_segments"] += res.retried
            stats["fallback_segments"] += res.fallback
            for rung, n in res.rungs.items():
                stats["rungs"][rung] = stats["rungs"].get(rung, 0) + n
            if progress:
                progress(res, done, total)
    return stats


# ---------------------------------------------------------------------------
# migration of an existing library
# ---------------------------------------------------------------------------

def migrate_record(record: Optional[dict], source: Optional[CourseSource], lang: str) -> Tuple[str, Optional[dict], str]:
    """Classify one existing file: ('keep'|'stale'|'unverifiable', record to write, why).

    keep: already has matching provenance, or can be backfilled because it matches today's English
    (same segment count, every number from the English present, validator says ship).
    stale: the course is in the current catalog but the file does not match it.
    unverifiable: no current English for this course, so nothing can be checked.
    """
    if not isinstance(record, dict):
        return "stale", None, "unreadable"
    if source is None:
        return "unverifiable", record, "course not in the current catalog sources"
    ok, why = is_current(record, source, lang)
    if ok:
        return "keep", record, "provenance matches"
    prov = record.get("provenance")
    if isinstance(prov, dict) and prov.get("source_sha256") and prov["source_sha256"] != source.sha:
        return "stale", None, "made from different English"
    verdict = judge_record(record, lang, source.segments, course_id=source.course_id)
    if verdict["verdict"] != SHIP:
        return "stale", None, "; ".join(verdict["reasons"][:2]) or "fails the validator"
    upgraded = dict(record)
    upgraded["provenance"] = {
        "pipeline": "backfill-1",
        "source_sha256": source.sha,
        "engine": str(record.get("source") or "unknown"),
        "model": "",
        "generated_at": "",
        "backfilled": True,
        "verified_by": "segment count + numbers + validator against the current English",
        "glossary_unreviewed": True,
    }
    return "keep", upgraded, "backfilled"
