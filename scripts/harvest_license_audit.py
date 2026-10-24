#!/usr/bin/env python3
"""Audit harvest corpora for sources Salareen may not use commercially.

Read-only by default. Writes a report plus a quarantine manifest; --apply marks the
flagged sources and their courses 'quarantined' (reversible, nothing is deleted, and
quarantined sources drop out of RAG retrieval).

  python3 scripts/harvest_license_audit.py                       # audit the usual locations
  python3 scripts/harvest_license_audit.py path/to/corpus.db     # audit specific databases
  python3 scripts/harvest_license_audit.py --apply               # mark quarantine candidates
  python3 scripts/harvest_license_audit.py --apply --include-needs-review
  python3 scripts/harvest_license_audit.py --restore             # undo --apply (audit: rows only)
  python3 scripts/harvest_license_audit.py --migrate-research R.db   # copy non-commercial text into the research corpus
  python3 scripts/harvest_license_audit.py --courses-dir output/harvest/courses

Usual locations: output/harvest/harvest_corpus.db and ~/.cache/aoep/harvest_corpus.db
(or $AOEP_HARVEST_CORPUS_DB). Run it on every machine that crawls (Mac, iBuyPower, Spark).
Not legal advice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared.harvest.license_audit import (  # noqa: E402
    BUCKET_QUARANTINE,
    BUCKET_REVIEW,
    apply_quarantine,
    audit_db,
    manifest,
    migrate_to_research,
    restore_quarantine,
    scan_course_files,
)
from aoep_shared.harvest.licensing import HarvestPolicy  # noqa: E402


def default_dbs() -> list[Path]:
    cands = [
        Path(os.environ["AOEP_HARVEST_CORPUS_DB"]) if os.environ.get("AOEP_HARVEST_CORPUS_DB") else None,
        ROOT / "output" / "harvest" / "harvest_corpus.db",
        Path.home() / ".cache" / "aoep" / "harvest_corpus.db",
    ]
    seen: list[Path] = []
    for c in cands:
        if c and c.is_file() and c not in seen:
            seen.append(c)
    return seen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dbs", nargs="*", help="corpus database files (default: the usual locations)")
    ap.add_argument("--out", default=str(ROOT / "output" / "harvest-audit"), help="where reports are written")
    ap.add_argument("--apply", action="store_true", help="mark quarantine candidates quarantined (reversible)")
    ap.add_argument("--include-needs-review", action="store_true", help="with --apply: also quarantine needs_review")
    ap.add_argument("--restore", action="store_true", help="undo --apply (only rows marked by this audit)")
    ap.add_argument("--allow-share-alike", action="store_true", help="treat CC BY-SA / GFDL as usable")
    ap.add_argument("--migrate-research", metavar="RESEARCH_DB",
                    help="copy research-eligible (non-commercial) text into this research corpus file; "
                         "never touches the product database, courses are not copied")
    ap.add_argument("--courses-dir", help="also scan *.course.json packages under this folder")
    ap.add_argument("--json", action="store_true", help="print the full JSON report to stdout")
    args = ap.parse_args(argv)

    dbs = [Path(p).expanduser() for p in args.dbs] or default_dbs()
    if not dbs:
        print("no corpus database found; pass a path", file=sys.stderr)
        return 2
    policy = HarvestPolicy(allow_share_alike=args.allow_share_alike)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    include = (BUCKET_QUARANTINE, BUCKET_REVIEW) if args.include_needs_review else (BUCKET_QUARANTINE,)
    status = 0
    for db in dbs:
        if not db.is_file():
            print(f"{db}: not found", file=sys.stderr)
            status = 2
            continue
        if args.restore:
            print(f"{db}: {restore_quarantine(db)}")
            continue
        report = audit_db(db, policy)
        tag = db.stem + "-" + hashlib.sha1(str(db.resolve()).encode()).hexdigest()[:6]
        (out / f"audit-{tag}.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        (out / f"quarantine-manifest-{tag}.json").write_text(
            json.dumps(manifest(report, include=include), indent=2), encoding="utf-8")
        (out / f"audit-{tag}.txt").write_text(report.text(), encoding="utf-8")
        print(report.text())
        if args.courses_dir:
            print("course packages:", json.dumps(scan_course_files(args.courses_dir, report)))
        if args.migrate_research:
            print(f"{db} -> {args.migrate_research}: {migrate_to_research(db, args.migrate_research, report, policy)}")
        if args.apply:
            print(f"{db}: {apply_quarantine(db, report, include=include)}")
        elif report.by_bucket.get(BUCKET_QUARANTINE):
            print(f"(read-only run; --apply would quarantine {report.by_bucket[BUCKET_QUARANTINE]} sources)")
        if args.json:
            print(json.dumps(report.to_dict(with_findings=False), indent=2))
        print(f"reports: {out}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
