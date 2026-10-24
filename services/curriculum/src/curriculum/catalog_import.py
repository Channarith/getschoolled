"""Import tooling for the Postgres catalog (used by scripts/catalog_import.py).

Three sources:
  * a harvest bundle directory (scripts/harvest_sync.py export format): lesson decks become
    multi-lesson courses (~8 lessons each) via aoep_shared.catalog_db.compose;
  * the harvest index database (output/harvest_index.db), which also knows each deck's quality tier;
  * an existing catalog JSON file (CATALOG_PATH from the in-memory store): courses move as-is.

Properties the user asked for:
  * product corpus only: decks whose license tier cannot serve in the product are rejected
    (reported with the reason, never silently dropped), and the store quarantines anything that
    slips through;
  * idempotent: course ids are derived from the decks' content hashes, and inserts never overwrite,
    so re-running or importing overlapping bundles adds nothing twice;
  * resumable: a state file remembers how many composed courses were already written;
  * dry-run by default in the CLI: it prints exactly what would happen.
"""

from __future__ import annotations

import gzip
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from aoep_shared.catalog_db.compose import ComposedCourse, DeckRef, compose_courses, license_tier

from .catalog import Course


@dataclass
class ImportReport:
    decks_seen: int = 0
    decks_already_imported: int = 0
    decks_rejected: int = 0
    rejected_by_reason: Dict[str, int] = field(default_factory=dict)
    courses_composed: int = 0
    courses_inserted: int = 0
    courses_skipped_existing: int = 0
    resumed_from: int = 0
    dry_run: bool = True
    problems: List[str] = field(default_factory=list)


def _first_text(bundle: Path, sha: str) -> str:
    obj = bundle / "courses" / sha[:2] / f"{sha}.json.gz"
    try:
        body = json.loads(gzip.decompress(obj.read_bytes()).decode("utf-8"))
        slides = body.get("slides") or []
        return str((slides[0].get("body") if slides else "") or "")
    except (OSError, ValueError):
        return ""


def decks_from_bundle(bundle_dir: str | Path, *, read_text: bool = True) -> Iterator[DeckRef]:
    bundle = Path(bundle_dir)
    for line in (bundle / "provenance.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        sha = rec["sha256"]
        yield DeckRef(
            sha256=sha,
            title=rec.get("title") or "",
            subject=rec.get("subject") or "general",
            language=rec.get("language") or "en",
            source_url=rec.get("source_url") or "",
            license=rec.get("license") or "",
            slides=int(rec.get("slides") or 0),
            quality_tier=0,
            first_text=_first_text(bundle, sha) if read_text else "",
            harvested_at=rec.get("harvested_at") or "",
            attribution={"source_url": rec.get("source_url") or "", "license": rec.get("license") or ""},
        )


def decks_from_index(index_db: str | Path) -> Iterator[DeckRef]:
    """Decks from the harvest index (tiers assigned at bundle import). Bodies stay in the object store."""
    conn = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for r in conn.execute(
            "SELECT sha256, title, subject, language, slides, source_url, license, tier, harvested_at "
            "FROM courses ORDER BY sha256"
        ):
            yield DeckRef(
                sha256=r["sha256"], title=r["title"] or "", subject=r["subject"] or "general",
                language=r["language"] or "en", source_url=r["source_url"] or "", license=r["license"] or "",
                slides=int(r["slides"] or 0), quality_tier=int(r["tier"] or 0), harvested_at=r["harvested_at"] or "",
                attribution={"source_url": r["source_url"] or "", "license": r["license"] or ""},
            )
    finally:
        conn.close()


def courses_from_json_catalog(path: str | Path) -> List[Course]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Course(**v) for v in (data.get("courses") or {}).values()]


def _sources_for(composed: ComposedCourse) -> List[dict]:
    return [
        {
            "deck_sha256": d.sha256,
            "source_url": d.source_url,
            "canonical_url": d.source_url,
            "license": d.license,
            "license_tier": license_tier(d.license),
            "attribution": d.attribution,
            "fetched_at": d.harvested_at,
        }
        for d in composed.decks
    ]


def compose_report(
    decks: Iterable[DeckRef], *, per_course: int = 8, allow_share_alike: bool = False,
    known_shas: Optional[set] = None,
) -> Tuple[List[ComposedCourse], ImportReport]:
    """Compose courses from decks. known_shas are lesson bodies already in some catalog course
    (store.known_deck_shas): they are left out, so adding decks to a series later only builds NEW
    courses and never reshuffles or duplicates lessons that are already published."""
    decks = list(decks)
    report = ImportReport(decks_seen=len(decks))
    if known_shas:
        fresh = [d for d in decks if d.sha256 not in known_shas]
        report.decks_already_imported = len(decks) - len(fresh)
        decks = fresh
    courses, rejected = compose_courses(decks, per_course=per_course, allow_share_alike=allow_share_alike)
    report.decks_rejected = len(rejected)
    for _deck, reason in rejected:
        key = reason.split(" (")[0]
        report.rejected_by_reason[key] = report.rejected_by_reason.get(key, 0) + 1
    report.courses_composed = len(courses)
    return courses, report


def write_courses(
    store,
    composed: List[ComposedCourse],
    report: ImportReport,
    *,
    batch: int = 500,
    dry_run: bool = True,
    state_file: Optional[str | Path] = None,
) -> ImportReport:
    """Write composed courses in batches. Idempotent; resumable through state_file."""
    report.dry_run = dry_run
    start = 0
    state = Path(state_file) if state_file else None
    if state and state.is_file():
        try:
            start = int(json.loads(state.read_text())["done"])
        except (ValueError, KeyError, OSError):
            start = 0
    report.resumed_from = start
    if dry_run:
        report.courses_skipped_existing = 0
        return report
    for i in range(start, len(composed), batch):
        chunk = composed[i:i + batch]
        courses = [Course(**c.payload) for c in chunk]
        sources = {c.course_id: _sources_for(c) for c in chunk}
        inserted, skipped = store.bulk_insert(courses, sources)
        report.courses_inserted += inserted
        report.courses_skipped_existing += skipped
        if state:
            state.write_text(json.dumps({"done": i + len(chunk), "total": len(composed)}))
    return report


def write_plain_courses(store, courses: List[Course], report: ImportReport, *, batch: int = 500,
                        dry_run: bool = True) -> ImportReport:
    report.dry_run = dry_run
    report.courses_composed = len(courses)
    if dry_run:
        return report
    for i in range(0, len(courses), batch):
        inserted, skipped = store.bulk_insert(courses[i:i + batch])
        report.courses_inserted += inserted
        report.courses_skipped_existing += skipped
    return report
