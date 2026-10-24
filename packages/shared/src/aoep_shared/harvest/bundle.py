"""Content-addressed bundles: move completed courses between machines without loss.

export_bundle(): reads one machine's harvest corpus DB + its *.course.json files and writes

  <bundle>/bundle.json            header: machine, counts, sha256 of the two files below
  <bundle>/manifest.jsonl         one line per object: {"sha256","bytes"}
  <bundle>/provenance.jsonl       one line per course: source URL, license, subject, ...
  <bundle>/courses/<aa>/<sha>.json.gz   immutable gzip objects named by content hash (same layout
                                        as the object store, so a bundle dir is itself a store root)

Objects are never rewritten, so a half-finished rsync can simply be run again
(`rsync -a --partial --ignore-existing`). import_bundle() verifies every hash, applies the
license gate, de-duplicates by content hash into an ObjectStore plus a SQLite index, and
NEVER deletes anything (not in the bundle, the store or the index).
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional

from .objectstore import (
    ObjectStore,
    canonical_bytes,
    content_sha256,
    course_key,
    pack_course,
)
from .quality import NearDuplicateIndex, assign_tier
from .sources import is_allowed

BUNDLE_FORMAT = 1


def _sha_file(path: Path) -> str:
    return content_sha256(path.read_bytes())


def license_gate(license: Optional[str], *, require_commercial: bool = True) -> tuple[bool, str]:
    """(ok, reason). Salareen sells subscriptions, so non-commercial licenses are refused by default.

    Uses sources.is_allowed() for the open-license allowlist; the NC check is explicit and local
    so it holds even while the allowlist still contains the cc-by-nc entries."""
    lic = (license or "").strip().lower().replace(" ", "-").replace("_", "-")
    if not is_allowed(lic):
        return False, f"license not allowed: {license!r}"
    if require_commercial and ("-nc" in lic or lic.endswith("nc") or "noncommercial" in lic):
        return False, f"non-commercial license cannot ship in a paid product: {license!r}"
    return True, ""


@dataclass
class ExportReport:
    courses: int = 0
    objects_written: int = 0
    objects_existing: int = 0
    skipped_missing_file: int = 0
    skipped_unreadable: int = 0


def _course_rows(corpus_db: Path) -> Iterator[sqlite3.Row]:
    conn = sqlite3.connect(f"file:{corpus_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield from conn.execute(
            "SELECT c.course_id, c.title, c.subject, c.composition_score, c.json_path, c.created_at, "
            "s.url AS source_url, s.license AS license, s.source_type AS source_type "
            "FROM courses c LEFT JOIN sources s ON s.url_key = c.url_key ORDER BY c.course_id"
        )
    finally:
        conn.close()


def export_bundle(
    corpus_db: str | Path,
    out_dir: str | Path,
    *,
    machine: str,
    repo_root: str | Path = ".",
    limit: Optional[int] = None,
) -> ExportReport:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(repo_root)
    report = ExportReport()
    manifest: Dict[str, int] = {}
    prov: List[dict] = []
    for row in _course_rows(Path(corpus_db)):
        if limit is not None and report.courses >= limit:
            break
        jp = Path(row["json_path"] or "")
        path = jp if jp.is_absolute() else root / jp
        if not path.is_file():
            report.skipped_missing_file += 1
            continue
        try:
            course = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            report.skipped_unreadable += 1
            continue
        sha, gz = pack_course(course)
        target = out / course_key(sha)
        if target.exists():
            report.objects_existing += 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".tmp")
            tmp.write_bytes(gz)
            tmp.replace(target)
            report.objects_written += 1
        manifest[sha] = target.stat().st_size
        prov.append(
            {
                "course_id": row["course_id"],
                "sha256": sha,
                "title": row["title"],
                "subject": row["subject"],
                "language": course.get("language", ""),
                "slides": len(course.get("slides") or []),
                "composition_score": row["composition_score"],
                "source_url": row["source_url"],
                "license": row["license"],
                "source_type": row["source_type"],
                "machine": machine,
                "harvested_at": row["created_at"],
            }
        )
        report.courses += 1
    (out / "manifest.jsonl").write_text(
        "".join(json.dumps({"sha256": s, "bytes": b}) + "\n" for s, b in sorted(manifest.items())),
        encoding="utf-8",
    )
    (out / "provenance.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in prov), encoding="utf-8"
    )
    header = {
        "format": BUNDLE_FORMAT,
        "machine": machine,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "courses": report.courses,
        "objects": len(manifest),
        "manifest_sha256": _sha_file(out / "manifest.jsonl"),
        "provenance_sha256": _sha_file(out / "provenance.jsonl"),
    }
    (out / "bundle.json").write_text(json.dumps(header, indent=2), encoding="utf-8")
    return report


INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
  sha256 TEXT PRIMARY KEY, course_id TEXT, title TEXT, subject TEXT, language TEXT, slides INTEGER,
  source_url TEXT, license TEXT, machine TEXT, tier INTEGER NOT NULL DEFAULT 0, tier_notes TEXT,
  harvested_at TEXT, imported_at TEXT NOT NULL, published_at TEXT);
CREATE INDEX IF NOT EXISTS idx_courses_tier ON courses(tier);
CREATE INDEX IF NOT EXISTS idx_courses_source ON courses(source_url);
CREATE TABLE IF NOT EXISTS rejected (
  sha256 TEXT, course_id TEXT, source_url TEXT, license TEXT, reason TEXT, bundle TEXT, at TEXT NOT NULL);
"""


def open_index(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(INDEX_SCHEMA)
    return conn


@dataclass
class ImportReport:
    imported: int = 0
    duplicates: int = 0
    rejected_license: int = 0
    rejected_integrity: int = 0
    tier1: int = 0
    near_duplicates: int = 0
    problems: List[str] = field(default_factory=list)


def verify_bundle(bundle_dir: str | Path) -> List[str]:
    """Header and file-level integrity; returns a list of problems (empty = OK)."""
    b = Path(bundle_dir)
    problems: List[str] = []
    try:
        header = json.loads((b / "bundle.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["bundle.json missing or unreadable"]
    if header.get("format") != BUNDLE_FORMAT:
        problems.append(f"unsupported bundle format {header.get('format')!r}")
    for name, key in (
        ("manifest.jsonl", "manifest_sha256"),
        ("provenance.jsonl", "provenance_sha256"),
    ):
        p = b / name
        if not p.is_file():
            problems.append(f"{name} missing")
        elif _sha_file(p) != header.get(key):
            problems.append(f"{name} does not match its recorded sha256")
    return problems


def import_bundle(
    bundle_dir: str | Path,
    store: ObjectStore,
    index: sqlite3.Connection,
    *,
    require_commercial: bool = True,
    corroborate: Optional[Callable[[dict], bool]] = None,
    dedup: Optional[NearDuplicateIndex] = None,
) -> ImportReport:
    b = Path(bundle_dir)
    report = ImportReport()
    report.problems = verify_bundle(b)
    if report.problems:
        return report
    now = datetime.now(timezone.utc).isoformat()
    dedup = dedup if dedup is not None else NearDuplicateIndex()
    for line in (b / "provenance.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        sha = rec["sha256"]
        ok, reason = license_gate(rec.get("license"), require_commercial=require_commercial)
        if not ok:
            index.execute(
                "INSERT INTO rejected VALUES (?,?,?,?,?,?,?)",
                (
                    sha,
                    rec.get("course_id"),
                    rec.get("source_url"),
                    rec.get("license"),
                    reason,
                    b.name,
                    now,
                ),
            )
            report.rejected_license += 1
            continue
        if index.execute("SELECT 1 FROM courses WHERE sha256=?", (sha,)).fetchone():
            report.duplicates += 1
            continue
        obj = b / course_key(sha)
        try:
            course = json.loads(gzip.decompress(obj.read_bytes()).decode("utf-8"))
            if content_sha256(canonical_bytes(course)) != sha:
                raise ValueError("hash mismatch")
        except Exception as exc:  # missing, truncated, corrupt, or tampered object
            index.execute(
                "INSERT INTO rejected VALUES (?,?,?,?,?,?,?)",
                (
                    sha,
                    rec.get("course_id"),
                    rec.get("source_url"),
                    rec.get("license"),
                    f"integrity: {exc}",
                    b.name,
                    now,
                ),
            )
            report.rejected_integrity += 1
            continue
        store.put(course_key(sha), obj.read_bytes())
        decision = assign_tier(course, key=sha, dedup=dedup, corroborate=corroborate)
        if decision.duplicate_of:
            report.near_duplicates += 1
        index.execute(
            "INSERT INTO courses (sha256,course_id,title,subject,language,slides,source_url,license,machine,"
            "tier,tier_notes,harvested_at,imported_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                sha,
                rec.get("course_id"),
                rec.get("title"),
                rec.get("subject"),
                rec.get("language"),
                rec.get("slides"),
                rec.get("source_url"),
                rec.get("license"),
                rec.get("machine"),
                decision.tier,
                "; ".join(decision.failures),
                rec.get("harvested_at"),
                now,
            ),
        )
        report.imported += 1
        report.tier1 += 1 if decision.tier == 1 else 0
    index.commit()
    return report
