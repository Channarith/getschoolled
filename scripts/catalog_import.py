#!/usr/bin/env python3
"""Import courses into the Postgres catalog. DRY-RUN unless --apply.

  # harvested decks -> multi-lesson courses (~8 lessons each), product-safe licenses only
  python3 scripts/catalog_import.py bundle output/incoming/spark-2026-10-24 --per-course 8
  python3 scripts/catalog_import.py bundle output/incoming/spark-2026-10-24 --apply
  # decks + quality tiers from the harvest index (written by scripts/harvest_sync.py import)
  python3 scripts/catalog_import.py index output/harvest_index.db --apply
  # the old in-memory/JSON catalog (CATALOG_PATH) -> Postgres, courses unchanged
  python3 scripts/catalog_import.py json /data/catalog.json --apply

Idempotent (re-running adds nothing) and resumable (--state FILE). Deck bodies are NOT copied here:
they already live in object storage (harvest_sync import); courses reference them as obj:<sha256>.
Non-commercial / unknown licenses are rejected and reported; share-alike only with --allow-share-alike
(off until legal review).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
sys.path.insert(0, str(ROOT / "services" / "curriculum" / "src"))

from curriculum import catalog_import as ci  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", choices=["bundle", "index", "json"])
    ap.add_argument("path")
    ap.add_argument("--dsn", default=os.environ.get("CATALOG_DATABASE_URL", ""))
    ap.add_argument("--apply", action="store_true", help="write to the database (default: dry run)")
    ap.add_argument("--per-course", type=int, default=8, help="target lessons per course")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--state", help="resume file (JSON); safe to delete to start over")
    ap.add_argument("--allow-share-alike", action="store_true",
                    help="also import CC BY-SA / GFDL decks (needs legal review first)")
    ap.add_argument("--no-text", action="store_true", help="do not read bodies for previews (faster)")
    args = ap.parse_args()

    store = None
    if args.apply and not args.dsn:
        print("no DSN: pass --dsn or set CATALOG_DATABASE_URL", file=sys.stderr)
        return 2
    if args.dsn:  # a dry run with a DSN also asks the database what is already imported
        from curriculum.catalog_pg import PgCatalogStore

        store = PgCatalogStore(args.dsn)

    if args.source == "json":
        courses = ci.courses_from_json_catalog(args.path)
        report = ci.ImportReport(decks_seen=len(courses))
        composed = None
    else:
        decks = list(ci.decks_from_bundle(args.path, read_text=not args.no_text) if args.source == "bundle"
                     else ci.decks_from_index(args.path))
        known = store.known_deck_shas(d.sha256 for d in decks) if store is not None else None
        composed, report = ci.compose_report(decks, per_course=args.per_course,
                                             allow_share_alike=args.allow_share_alike, known_shas=known)
        courses = None
    if composed is not None:
        report = ci.write_courses(store, composed, report, batch=args.batch, dry_run=not args.apply,
                                  state_file=args.state)
    else:
        report = ci.write_plain_courses(store, courses, report, batch=args.batch, dry_run=not args.apply)
    if store is not None:
        with store.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT catalog_refresh_facets()")
        store.close()
    print(json.dumps(report.__dict__, indent=2))
    if not args.apply:
        print("DRY RUN: nothing was written. Re-run with --apply to import.")
    return 1 if report.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
