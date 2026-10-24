"""Validate a translation library before anything ships.

Layout checked: <root>/<course_id>/<lang>.json, each a record written by
course_translation_library.save_translation (a "segments" list of heading/text).
English source text, when known, comes from the audio catalog (or a caller dict);
without it the checks that need English are skipped and peer languages are used
for the segment count.

Verdicts per file: ship (passes every automated check), hold (needs a person to
look), reject (do not ship). "ship" still means machine translation that has not
been reviewed by a human.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .course_translation_library import TARGET_LANGUAGES
from .translation_review import unit_key

SHIP, HOLD, REJECT = "ship", "hold", "reject"

_RANGES: Dict[str, List[Tuple[int, int]]] = {
    "km": [(0x1780, 0x17FF), (0x19E0, 0x19FF)],
    "th": [(0x0E00, 0x0E7F)],
    "hi": [(0x0900, 0x097F)],
    "bn": [(0x0980, 0x09FF)],
    "ur": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "fa": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "ar": [(0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)],
    "he": [(0x0590, 0x05FF)],
    "ru": [(0x0400, 0x04FF)],
    "uk": [(0x0400, 0x04FF)],
    "el": [(0x0370, 0x03FF), (0x1F00, 0x1FFF)],
    "zh": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],
    "ja": [(0x4E00, 0x9FFF), (0x3040, 0x309F), (0x30A0, 0x30FF)],
    "ko": [(0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)],
}
_LATIN_LANGS = {"es", "fr", "de", "it", "pt", "nl", "pl", "tr", "id", "sw", "cs", "vi"}
_VI_MARKS = set("ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")

# Typical target/source character-count ratio per language, measured on the Grok-seeded
# library (median over segments of 40+ characters). A segment is an outlier below
# 0.45x or above 2.2x of that: truncation and runaway output are the usual causes.
_TYPICAL_RATIO: Dict[str, float] = {
    "zh": 0.34, "ja": 0.45, "ko": 0.75, "km": 1.05, "th": 1.0, "ar": 0.9, "he": 0.85,
    "fa": 0.95, "ur": 1.0, "hi": 1.05, "bn": 1.0, "ru": 1.0,
}


def _ratio_band(lang: str) -> Tuple[float, float]:
    typical = _TYPICAL_RATIO.get(lang, 1.0)
    return 0.45 * typical, 2.2 * typical

_MARKUP = re.compile(
    r"</?[a-zA-Z][^>]{0,80}>|\*\*|__|\[[^\]]{1,40}\]\([^)]*\)|&[a-z]{2,6};|<unk>|</s>|<pad>|\[INST\]|\[/INST\]|```"
)
_URL = re.compile(r"https?://[^\s)>\]]+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_WORD_LOOP = re.compile(r"(\b\w+\b)(?:\W+\1\b){5,}", re.UNICODE)
_CHAR_LOOP = re.compile(r"(.{2,14}?)\1{5,}", re.DOTALL)
_PARTIAL = re.compile(r"\.(partial|tmp|part|bak|orig)$|~$", re.IGNORECASE)


def _letters(text: str) -> List[str]:
    return [c for c in text if unicodedata.category(c)[0] in ("L", "M")]


def script_fraction(text: str, lang: str) -> Optional[float]:
    """Share of letters/marks in the script expected for ``lang`` (None = not checkable)."""
    letters = _letters(text)
    if len(letters) < 8:
        return None
    if lang in _RANGES:
        ranges = _RANGES[lang]
        hit = sum(1 for c in letters if any(lo <= ord(c) <= hi for lo, hi in ranges))
        return hit / len(letters)
    if lang in _LATIN_LANGS:
        latin = sum(1 for c in letters if "LATIN" in unicodedata.name(c, ""))
        return latin / len(letters)
    return None


def vietnamese_marks(text: str) -> float:
    letters = _letters(text)
    if not letters:
        return 0.0
    return sum(1 for c in letters if c in _VI_MARKS) / len(letters)


def digits_to_ascii(text: str) -> str:
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


def numbers_in(text: str) -> List[str]:
    return [n.replace(",", ".") for n in _NUMBER.findall(digits_to_ascii(text))]


def has_loop(text: str) -> bool:
    return bool(_WORD_LOOP.search(text) or _CHAR_LOOP.search(text))


def _tokens(text: str) -> set:
    return set(re.findall(r"\w+", text.lower()))


def unchanged_from_source(source: str, target: str) -> bool:
    a, b = _tokens(source), _tokens(target)
    if len(a) < 4 or not b:
        return False
    return len(a & b) / len(a | b) >= 0.9


def _detect(text: str) -> Optional[str]:
    try:
        from langdetect import DetectorFactory, detect  # type: ignore

        DetectorFactory.seed = 0
        return detect(text)
    except Exception:
        return None


def _seg_findings(
    lang: str, heading: str, text: str, src: Optional[Dict[str, str]], langid: bool
) -> List[str]:
    out: List[str] = []
    if not heading.strip() or not text.strip():
        return ["empty"]
    whole = f"{heading} {text}"
    frac = script_fraction(whole, lang)
    if frac is not None:
        need = 0.55 if lang in _RANGES else 0.8
        if frac < need:
            out.append("wrong_script")
    if lang == "vi" and len(_letters(text)) >= 60 and vietnamese_marks(text) < 0.04:
        out.append("wrong_script")
    if has_loop(whole):
        out.append("degenerate_loop")
    if _MARKUP.search(whole):
        out.append("leftover_markup")
    if src:
        s_text = src.get("text", "")
        if unchanged_from_source(s_text, text):
            out.append("unchanged_from_english")
        if len(s_text) >= 40:
            lo, hi = _ratio_band(lang)
            ratio = len(text) / max(1, len(s_text))
            if ratio < lo or ratio > hi:
                out.append("length_outlier")
        # Years are often rewritten ("1870s" -> "19th century"), so they are not compared.
        s_nums = [n for n in numbers_in(s_text) if not (len(n) == 4 and n.isdigit() and 1000 <= int(n) <= 2100)]
        if len(s_nums) >= 2:
            t_nums = set(numbers_in(text))
            missing = [n for n in s_nums if n not in t_nums]
            if len(missing) * 2 >= len(s_nums):
                out.append("number_mismatch")
        urls = _URL.findall(s_text)
        if urls and any(u.rstrip(".,;") not in text for u in urls):
            out.append("url_mismatch")
    if langid and len(_letters(text)) >= 80 and lang in _LATIN_LANGS | {"ru", "uk", "el"}:
        guess = _detect(text)
        if guess == "en":
            out.append("language_is_english")
    return out


_REJECT_ANY = {"empty", "degenerate_loop", "leftover_markup"}
_FRACTION_REJECT = {"wrong_script", "unchanged_from_english", "language_is_english"}
_HOLD = {"length_outlier", "number_mismatch", "url_mismatch"}


def judge_file(
    path: Path,
    lang: str,
    source_segments: Optional[List[Dict[str, str]]],
    langid: bool = False,
) -> Dict[str, Any]:
    """Validate one file. Returns a row with verdict, reasons and light stats."""
    row: Dict[str, Any] = {
        "course_id": path.parent.name,
        "language": lang,
        "path": str(path),
        "bytes": 0,
        "segments": 0,
        "verdict": REJECT,
        "reasons": [],
        "counts": {},
        "hashes": [],
        "source": "",
    }
    try:
        raw = path.read_bytes()
        row["bytes"] = len(raw)
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        row["reasons"] = [f"parse_error: {type(exc).__name__}"]
        return row
    return _judge_parsed(row, data, lang, source_segments, langid)


def judge_record(
    data: Any,
    lang: str,
    source_segments: Optional[List[Dict[str, str]]],
    langid: bool = False,
    course_id: str = "",
) -> Dict[str, Any]:
    """Judge a translation record that is already in memory (same checks as judge_file)."""
    row: Dict[str, Any] = {
        "course_id": course_id or (data.get("course_id", "") if isinstance(data, dict) else ""),
        "language": lang,
        "path": "",
        "bytes": 0,
        "segments": 0,
        "verdict": REJECT,
        "reasons": [],
        "counts": {},
        "hashes": [],
        "source": "",
    }
    return _judge_parsed(row, data, lang, source_segments, langid)


def _judge_parsed(
    row: Dict[str, Any],
    data: Any,
    lang: str,
    source_segments: Optional[List[Dict[str, str]]],
    langid: bool,
) -> Dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("segments"), list):
        row["reasons"] = ["bad_structure"]
        return row
    row["source"] = str(data.get("source") or "")
    if data.get("language") and data.get("language") != lang:
        row["reasons"].append("language_field_mismatch")
    if data.get("course_id") and not str(data["course_id"]).strip():
        row["reasons"].append("bad_course_id")
    segs = [s for s in data["segments"] if isinstance(s, dict)]
    if len(segs) != len(data["segments"]):
        row["reasons"].append("bad_structure")
        return row
    row["segments"] = len(segs)
    if not segs:
        row["reasons"] = ["no_segments"]
        return row

    expected = None
    if source_segments is not None:
        expected = [s for s in source_segments if s.get("heading") and s.get("text")]
        if len(expected) != len(segs):
            row["reasons"].append(f"segment_count_mismatch ({len(segs)} vs source {len(expected)})")
    counts: Counter = Counter()
    for i, seg in enumerate(segs):
        heading, text = str(seg.get("heading") or ""), str(seg.get("text") or "")
        src = expected[i] if expected is not None and len(expected) == len(segs) else None
        for finding in _seg_findings(lang, heading, text, src, langid):
            counts[finding] += 1
        row["hashes"].append(unit_key(heading, text) if len(_letters(text)) >= 30 else "")
    row["counts"] = dict(counts)
    n = len(segs)
    reject = bool(row["reasons"] and any(r.startswith(("segment_count", "bad_")) for r in row["reasons"]))
    hold = False
    for finding, c in counts.items():
        if finding in _REJECT_ANY:
            reject = True
            row["reasons"].append(f"{finding} in {c}/{n} segments")
        elif finding in _FRACTION_REJECT:
            if c / n >= 0.2:
                reject = True
            else:
                hold = True
            row["reasons"].append(f"{finding} in {c}/{n} segments")
        elif finding in _HOLD:
            hold = True
            row["reasons"].append(f"{finding} in {c}/{n} segments")
    if "language_field_mismatch" in row["reasons"]:
        hold = True
    row["verdict"] = REJECT if reject else HOLD if hold else SHIP
    return row


def scan_library(root: Path) -> Tuple[List[Tuple[Path, str]], List[Dict[str, str]]]:
    """Return ([(file, lang)], stray files) for <root>/<course>/<file>."""
    files: List[Tuple[Path, str]] = []
    stray: List[Dict[str, str]] = []
    langs = set(TARGET_LANGUAGES) | {"en"}
    for entry in sorted(root.iterdir()):
        if entry.is_file():
            if entry.name != "index.json":
                stray.append({"path": str(entry), "why": "file in library root"})
            continue
        children = sorted(entry.iterdir())
        if not any(c.suffix == ".json" for c in children):
            stray.append({"path": str(entry), "why": "course folder without any json"})
        for child in children:
            if child.is_dir():
                stray.append({"path": str(child), "why": "nested folder"})
            elif _PARTIAL.search(child.name) or child.name.endswith(".lock"):
                stray.append({"path": str(child), "why": "unfinished or temporary file"})
            elif child.suffix == ".json" and child.stem in langs:
                files.append((child, child.stem))
            else:
                stray.append({"path": str(child), "why": "not <language>.json"})
    return files, stray


def validate_library(
    root: Path,
    sources: Optional[Dict[str, List[Dict[str, str]]]] = None,
    languages: Optional[Iterable[str]] = None,
    langid: bool = False,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Validate every file under ``root``. ``sources``: course_id -> English segments."""
    root = Path(root)
    files, stray = scan_library(root)
    wanted = set(languages) if languages else None
    rows: List[Dict[str, Any]] = []
    for path, lang in files:
        if lang == "en" or (wanted and lang not in wanted):
            continue
        if limit and len(rows) >= limit:
            break
        src = sources.get(path.parent.name) if sources else None
        rows.append(judge_file(path, lang, src, langid))

    # cross-file checks: peer segment counts and the same text copied across languages
    by_course: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_course[r["course_id"]].append(r)
    for course, group in by_course.items():
        if sources and course in sources:
            continue
        counts = [r["segments"] for r in group if r["segments"] and not r["reasons"][:1] == ["bad_structure"]]
        if len(counts) >= 3:
            mode, freq = Counter(counts).most_common(1)[0]
            if freq >= 3:
                for r in group:
                    if r["segments"] and r["segments"] != mode:
                        r["reasons"].append(f"peer_count_mismatch ({r['segments']} vs {mode} in other languages)")
                        if r["verdict"] == SHIP:
                            r["verdict"] = HOLD
        seen: Dict[Tuple[int, str], str] = {}
        for r in group:
            for i, h in enumerate(r["hashes"]):
                if not h:
                    continue
                prior = seen.setdefault((i, h), r["language"])
                if prior != r["language"] and r["language"] not in {"es", "pt", "it", "fr"} and prior not in {"es", "pt", "it", "fr"}:
                    msg = f"same text as {prior} at segment {i + 1}"
                    if msg not in r["reasons"]:
                        r["reasons"].append(msg)
                    if r["verdict"] == SHIP:
                        r["verdict"] = HOLD

    per_lang: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        d = per_lang.setdefault(
            r["language"], {"files": 0, SHIP: 0, HOLD: 0, REJECT: 0, "segments": 0, "bytes": 0, "top_reasons": Counter()}
        )
        d["files"] += 1
        d[r["verdict"]] += 1
        d["segments"] += r["segments"]
        d["bytes"] += r["bytes"]
        for reason in r["reasons"]:
            d["top_reasons"][re.split(r" [(i]", reason)[0]] += 1
    for d in per_lang.values():
        d["top_reasons"] = dict(d["top_reasons"].most_common(6))

    distinct = len({h for r in rows for h in r["hashes"] if h})
    total_segments = sum(1 for r in rows for h in r["hashes"] if h)
    for r in rows:
        r.pop("hashes", None)
    shippable = [
        {"course_id": r["course_id"], "language": r["language"], "path": str(Path(r["path"]).relative_to(root)),
         "bytes": r["bytes"], "sha256": r.get("sha256", ""), "segments": r["segments"], "source": r["source"]}
        for r in rows
        if r["verdict"] == SHIP
    ]
    return {
        "root": str(root),
        "had_english_source": bool(sources),
        "files": len(rows),
        "courses": len(by_course),
        "verdicts": dict(Counter(r["verdict"] for r in rows)),
        "per_language": per_lang,
        "stray": stray,
        "distinct_units": distinct,
        "total_units": total_segments,
        "rows": rows,
        "shippable": shippable,
    }


def render_text(report: Dict[str, Any]) -> str:
    v = report["verdicts"]
    lines = [
        f"Translation validation: {report['root']}",
        f"{report['files']} files, {report['courses']} courses; ship {v.get('ship', 0)}, hold {v.get('hold', 0)}, reject {v.get('reject', 0)}",
        "English source: " + ("yes (segment counts and numbers checked)" if report["had_english_source"] else "no (peer languages used for counts)"),
        "ship = passes the automated checks; it is still machine translation until staff review it.",
        "",
        f"{'LANG':<5} {'FILES':>6} {'SHIP':>6} {'HOLD':>6} {'REJECT':>7}  TOP REASONS",
    ]
    for lang, d in sorted(report["per_language"].items(), key=lambda kv: -kv[1]["files"]):
        reasons = ", ".join(f"{k} x{c}" for k, c in d["top_reasons"].items())
        lines.append(f"{lang:<5} {d['files']:>6} {d[SHIP]:>6} {d[HOLD]:>6} {d[REJECT]:>7}  {reasons[:110]}")
    if report["total_units"]:
        lines.append("")
        lines.append(f"{report['total_units']} segments, {report['distinct_units']} distinct (reuse could save {report['total_units'] - report['distinct_units']} reviews)")
    if report["stray"]:
        lines.append("")
        lines.append(f"{len(report['stray'])} stray files or folders (excluded), first few:")
        lines.extend(f"  {s['path']} - {s['why']}" for s in report["stray"][:8])
    return "\n".join(lines)
