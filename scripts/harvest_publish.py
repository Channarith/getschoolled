#!/usr/bin/env python3
"""Publish imported decks to production gently (resumable, rate-limited, circuit-broken).

  # always look first
  python3 scripts/harvest_publish.py --dry-run --min-tier 1
  # real run: small, tier-1 only, 1 request/second, stop after 500
  INTERNAL_TOKEN=... python3 scripts/harvest_publish.py --sink curriculum \\
      --base-url https://www.salareen.com --min-tier 1 --rate 1 --max-total 500
  # write catalog index records into the object store instead (source of truth for a DB-backed catalog)
  python3 scripts/harvest_publish.py --sink objectstore --min-tier 1

The curriculum catalog today is an in-memory dict per replica with a whole-file JSON autosave on
every write (see docs/million-courses.txt, section 6): use --sink curriculum only for small,
supervised batches (tens of thousands at most) and watch the pods. Safe to Ctrl-C and re-run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from aoep_shared.harvest.bundle import open_index  # noqa: E402
from aoep_shared.harvest.objectstore import open_store  # noqa: E402
from aoep_shared.harvest.publish import (
    CurriculumHttpSink,
    ObjectStoreIndexSink,
    PublishConfig,
    Publisher,
)  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--index", default="output/harvest_index.db")
    ap.add_argument("--store")
    ap.add_argument("--sink", choices=["curriculum", "objectstore"], default="curriculum")
    ap.add_argument(
        "--base-url", default=os.environ.get("CURRICULUM_URL", "https://www.salareen.com")
    )
    ap.add_argument(
        "--min-tier",
        type=int,
        default=1,
        help="1 = auto-validated only (default); 0 includes unreviewed machine output",
    )
    ap.add_argument("--rate", type=float, default=1.0, help="max requests per second")
    ap.add_argument("--burst", type=int, default=2)
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--max-total", type=int)
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--breaker-failures", type=int, default=5)
    ap.add_argument("--breaker-cooldown", type=float, default=120.0)
    ap.add_argument("--no-check-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    store = open_store(a.store)
    if a.sink == "curriculum":
        token = os.environ.get("INTERNAL_TOKEN", "")
        if not token and not a.dry_run:
            print("INTERNAL_TOKEN is required for --sink curriculum", file=sys.stderr)
            return 2
        sink = CurriculumHttpSink(a.base_url, token)
    else:
        sink = ObjectStoreIndexSink(store)
    cfg = PublishConfig(
        rate_per_sec=a.rate,
        burst=a.burst,
        batch_size=a.batch,
        max_retries=a.retries,
        breaker_failures=a.breaker_failures,
        breaker_cooldown=a.breaker_cooldown,
        min_tier=a.min_tier,
        max_total=a.max_total,
        dry_run=a.dry_run,
        check_existing=not a.no_check_existing,
    )
    report = Publisher(open_index(a.index), store, sink, cfg).run()
    print(json.dumps(report.__dict__, indent=2))
    return 0 if report.stopped in ("done", "max_total") else 1


if __name__ == "__main__":
    raise SystemExit(main())
