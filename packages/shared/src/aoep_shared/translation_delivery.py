"""Delivery of validated course translations from the machines that make them to the cluster.

The v2 pipeline writes ``<root>/<course>/<lang>.json`` on the Spark and on kalel. This module is the shared contract between
the publisher (``scripts/publish_translations.py``, runs on the owner's Mac) and the service-side mirror
(``translation_store``): a delivery manifest ``_delivery.json`` that lists exactly which files may be served, with their sha256.

Nothing here talks to the network. The merge rules (only current + validated files, newest wins, a valid file is never replaced
by a stale or held one) are pure functions so they can be tested without S3.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

DELIVERY_NAME = "_delivery.json"
DELIVERY_VERSION = 1
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_MANIFEST_BYTES = 5 * 1024 * 1024

# <course>/<lang>.json: the course folder name is safe_course_id() output, the language is a short code (yue, tl, zh, en-gb...).
_REL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,150}/[a-z]{2,3}(?:-[a-z0-9]{2,8})?\.json$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_rel(rel: str) -> bool:
    """A library-relative file name that cannot escape the mirror folder (no '..', no absolute paths, no odd characters)."""
    return bool(isinstance(rel, str) and _REL_RE.match(rel) and ".." not in rel.split("/")[0])


def rel_for(course_id: str, lang: str) -> str:
    from .course_translation_library import normalize_translation_language, safe_course_id

    return f"{safe_course_id(course_id)}/{normalize_translation_language(lang) or lang}.json"


def build_manifest(files: Mapping[str, Mapping[str, Any]], *, pipeline: str, generated_at: Optional[str] = None) -> Dict[str, Any]:
    clean: Dict[str, Dict[str, Any]] = {}
    for rel, meta in sorted(files.items()):
        if not valid_rel(rel):
            raise ValueError(f"unsafe file name in manifest: {rel!r}")
        sha = str(meta.get("sha256") or "")
        if not _SHA_RE.match(sha):
            raise ValueError(f"bad sha256 for {rel}")
        clean[rel] = {
            "sha256": sha,
            "size": int(meta.get("size") or 0),
            "validated_at": str(meta.get("validated_at") or ""),
            "source_sha256": str(meta.get("source_sha256") or ""),
        }
    return {
        "version": DELIVERY_VERSION,
        "pipeline": str(pipeline),
        "generated_at": generated_at or utc_now(),
        "count": len(clean),
        "files": clean,
    }


def parse_manifest(raw: Any) -> Optional[Dict[str, Any]]:
    """Strict parse. Anything unexpected (wrong version, unsafe names, bad hashes, oversize entries) returns None: serve nothing new."""
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > MAX_MANIFEST_BYTES:
            return None
        try:
            raw = json.loads(bytes(raw).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
    if not isinstance(raw, dict) or raw.get("version") != DELIVERY_VERSION:
        return None
    files = raw.get("files")
    if not isinstance(files, dict):
        return None
    clean: Dict[str, Dict[str, Any]] = {}
    for rel, meta in files.items():
        if not valid_rel(rel) or not isinstance(meta, dict):
            return None
        sha = meta.get("sha256")
        size = meta.get("size")
        if not isinstance(sha, str) or not _SHA_RE.match(sha) or not isinstance(size, int) or not (0 < size <= MAX_FILE_BYTES):
            return None
        clean[rel] = {"sha256": sha, "size": size, "validated_at": str(meta.get("validated_at") or ""),
                      "source_sha256": str(meta.get("source_sha256") or "")}
    return {"version": DELIVERY_VERSION, "pipeline": str(raw.get("pipeline") or ""), "generated_at": str(raw.get("generated_at") or ""),
            "count": len(clean), "files": clean}


def light_record_check(data: bytes, rel: str) -> Tuple[bool, str]:
    """Cheap sanity check the mirror runs on every downloaded file, before the sha256 is trusted for placement.

    The full validator (provenance matches today's English, v2 verdict) runs in the publisher and again at read time in
    ``audio_search.shippable``; this only refuses files that are obviously not a translation of the file name they claim.
    """
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, "not_json"
    if not isinstance(record, dict) or not isinstance(record.get("segments"), list) or not record["segments"]:
        return False, "no_segments"
    if not isinstance(record.get("provenance"), dict):
        return False, "no_provenance"
    lang = rel.rsplit("/", 1)[1][:-5]
    from .course_translation_library import normalize_translation_language

    declared = normalize_translation_language(str(record.get("language") or ""))
    if declared and declared != (normalize_translation_language(lang) or lang):
        return False, "wrong_language"
    return True, "ok"


@dataclass
class Candidate:
    source: str          # label of the machine/folder it came from ("spark", "kalel")
    path: Path
    record: Dict[str, Any]
    generated_at: str


@dataclass
class Selected:
    rel: str
    path: Path
    sha256: str
    size: int
    validated_at: str
    source_sha256: str
    origin: str


IsCurrent = Callable[[Optional[dict], Any, str], Tuple[bool, str]]


def _load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def select_valid(
    roots: Mapping[str, Path],
    sources: Iterable[Any],
    languages: Sequence[str],
    *,
    is_current: IsCurrent,
    previous: Optional[Mapping[str, Mapping[str, Any]]] = None,
    previous_dir: Optional[Path] = None,
    now: Optional[str] = None,
) -> Tuple[List[Selected], List[Dict[str, str]]]:
    """Pick, for every (course, language), the single file to publish.

    A candidate counts only when ``is_current`` says it is a translation of today's English that passes the validator
    (so held, rejected, stale, partial and unprovenanced files are never picked). Among valid candidates the newest
    ``provenance.generated_at`` wins, ties go to the earlier-listed root. A file already published and still valid is kept
    unless a strictly newer valid candidate exists; an invalid candidate never replaces a valid published file.
    Returns (selected, skipped) where skipped explains each course/language with no valid file.
    """
    now = now or utc_now()
    chosen: List[Selected] = []
    skipped: List[Dict[str, str]] = []
    order = list(roots)
    for src in sources:
        for lang in languages:
            rel = rel_for(src.course_id, lang)
            best: Optional[Candidate] = None
            reasons: List[str] = []
            for label in order:
                path = roots[label] / rel
                if not path.is_file():
                    continue
                record = _load(path)
                ok, why = is_current(record, src, lang)
                if not ok:
                    reasons.append(f"{label}:{why.split(':')[0]}")
                    continue
                stamp = str(((record or {}).get("provenance") or {}).get("generated_at") or "")
                if best is None or stamp > best.generated_at:
                    best = Candidate(label, path, record or {}, stamp)
            # An already published, still-valid file is kept unless something strictly newer and valid exists.
            if previous_dir is not None and previous is not None and rel in previous:
                kept = previous_dir / rel
                krec = _load(kept) if kept.is_file() else None
                kok, _ = is_current(krec, src, lang) if krec else (False, "missing")
                if kok:
                    kstamp = str(((krec or {}).get("provenance") or {}).get("generated_at") or "")
                    if best is None or kstamp >= best.generated_at:
                        best = Candidate("published", kept, krec or {}, kstamp)
            if best is None:
                if reasons:
                    skipped.append({"course_id": src.course_id, "language": lang, "why": ",".join(reasons)})
                continue
            data = best.path.read_bytes()
            ok, why = light_record_check(data, rel)
            if not ok or len(data) > MAX_FILE_BYTES:
                skipped.append({"course_id": src.course_id, "language": lang, "why": f"{best.source}:{why}"})
                continue
            chosen.append(Selected(rel, best.path, sha256_bytes(data), len(data), now, str(((best.record.get('provenance') or {}).get('source_sha256')) or ""), best.source))
    return chosen, skipped


def plan_upload(new_files: Mapping[str, Mapping[str, Any]], remote_files: Optional[Mapping[str, Mapping[str, Any]]]) -> Dict[str, List[str]]:
    """What a publish run has to do against the bucket's current manifest.

    ``upload`` = new files or files whose sha256 changed; ``unchanged`` are skipped (no transfer); ``withdrawn`` are in the remote
    manifest but not in the new one (they stop being served as soon as the new manifest is written; the objects are only deleted with --prune).
    """
    remote = remote_files or {}
    upload = sorted(r for r, m in new_files.items() if (remote.get(r) or {}).get("sha256") != m.get("sha256"))
    unchanged = sorted(r for r in new_files if r not in set(upload))
    withdrawn = sorted(r for r in remote if r not in new_files)
    return {"upload": upload, "unchanged": unchanged, "withdrawn": withdrawn}


def drop_matching(files: Mapping[str, Mapping[str, Any]], *, lang: Optional[str] = None, course: Optional[str] = None) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Manifest entries left after withdrawing a language and/or a course, plus the removed names."""
    from .course_translation_library import normalize_translation_language, safe_course_id

    code = (normalize_translation_language(lang) or lang) if lang else None
    cid = safe_course_id(course) if course else None
    kept: Dict[str, Dict[str, Any]] = {}
    removed: List[str] = []
    for rel, meta in files.items():
        folder, name = rel.split("/", 1)
        if (code is None or name == f"{code}.json") and (cid is None or folder == cid):
            removed.append(rel)
        else:
            kept[rel] = dict(meta)
    return kept, sorted(removed)
