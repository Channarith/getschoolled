#!/usr/bin/env python3
"""Apply / inspect the catalog database schema (forward-only migrations).

  python3 scripts/catalog_migrate.py status                 # what is applied / pending
  python3 scripts/catalog_migrate.py up                     # apply pending migrations
  python3 scripts/catalog_migrate.py up --dry-run

DSN: --dsn or CATALOG_DATABASE_URL (postgresql://user:pass@host:5432/dbname). Needs psycopg:
  pip install 'psycopg[binary,pool]'
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from aoep_shared.catalog_db import migrate  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["status", "up"])
    ap.add_argument("--dsn", default=os.environ.get("CATALOG_DATABASE_URL", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.dsn:
        print("no DSN: pass --dsn or set CATALOG_DATABASE_URL", file=sys.stderr)
        return 2
    conn = migrate.connect(args.dsn)
    try:
        report = migrate.migrate(conn, dry_run=(args.command == "status" or args.dry_run))
    finally:
        conn.close()
    for name in report.already:
        print(f"  applied   {name}")
    for name in report.applied:
        print(f"  APPLIED   {name}")
    for name in report.pending:
        print(f"  pending   {name}")
    for problem in report.problems:
        print(f"  PROBLEM   {problem}", file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
