#!/usr/bin/env python3
"""Move harvested courses between the three machines, safely (never deletes anything).

  # on each worker machine (spark, kalel, mac): bundle what it has finished
  python3 scripts/harvest_sync.py export --corpus output/harvest/harvest_corpus.db \\
      --out output/bundles/spark-$(date +%F) --machine spark
  # copy it to the aggregator (resumable; objects are immutable so --ignore-existing is safe)
  rsync -a --partial --ignore-existing output/bundles/spark-2026-10-24/ mac:~/getschoolled/output/incoming/spark-2026-10-24/
  # on the aggregator: check, then import (license gate + dedup by content hash)
  python3 scripts/harvest_sync.py verify output/incoming/spark-2026-10-24
  python3 scripts/harvest_sync.py import output/incoming/spark-2026-10-24
  python3 scripts/harvest_sync.py status
  python3 scripts/harvest_sync.py shards                      # who owns which hosts
  python3 scripts/harvest_sync.py shards https://openstax.org/ https://ocw.mit.edu/

Defaults: store output/object_store (or OBJECT_STORE_DIR, or --store s3 using OBJECT_STORE_* env),
index output/harvest_index.db. Non-commercial licenses are always rejected (they live in the research corpus, which is never bundled
or published; --allow-noncommercial now only prints that error)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from aoep_shared.harvest.bundle import export_bundle, import_bundle, open_index, verify_bundle  # noqa: E402
from aoep_shared.harvest.objectstore import open_store  # noqa: E402
from aoep_shared.harvest.shard import DEFAULT_CONFIG_PATH, ShardMap  # noqa: E402

DEFAULT_INDEX = "output/harvest_index.db"


def cmd_export(a) -> int:
    rep = export_bundle(a.corpus, a.out, machine=a.machine, repo_root=a.repo_root, limit=a.limit)
    print(json.dumps(rep.__dict__, indent=2))
    print(
        f"bundle: {a.out}  ({rep.courses} courses). Copy with: rsync -a --partial --ignore-existing {a.out}/ HOST:DEST/"
    )
    return 0 if rep.courses else 1


def cmd_verify(a) -> int:
    problems = verify_bundle(a.bundle)
    print("OK" if not problems else "\n".join(problems))
    return 1 if problems else 0


def cmd_import(a) -> int:
    if a.allow_noncommercial:
        raise SystemExit(
            "harvest_sync: non-commercial courses cannot be imported into the product index. They stay in the "
            "research corpus (internal experiments only, never published)."
        )
    rep = import_bundle(
        a.bundle,
        open_store(a.store),
        open_index(a.index),
        require_commercial=True,
        # Courses reach production through this gate, so a license that was never confirmed on the
        # source page (courses made before license tiers) is held back unless you say otherwise.
        require_verified=not a.allow_unverified,
    )
    print(json.dumps(rep.__dict__, indent=2))
    return 1 if rep.problems else 0


def cmd_status(a) -> int:
    conn = open_index(a.index)
    q = lambda sql: conn.execute(sql).fetchall()  # noqa: E731
    out = {
        "courses": q("SELECT COUNT(*) FROM courses")[0][0],
        "by_tier": {r[0]: r[1] for r in q("SELECT tier, COUNT(*) FROM courses GROUP BY tier")},
        "by_machine": {
            r[0]: r[1] for r in q("SELECT machine, COUNT(*) FROM courses GROUP BY machine")
        },
        "by_license": {
            r[0]: r[1] for r in q("SELECT license, COUNT(*) FROM courses GROUP BY license")
        },
        "published": q("SELECT COUNT(*) FROM courses WHERE published_at IS NOT NULL")[0][0],
        "rejected": {
            r[0]: r[1]
            for r in q(
                "SELECT reason, COUNT(*) FROM rejected GROUP BY reason ORDER BY 2 DESC LIMIT 10"
            )
        },
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_shards(a) -> int:
    m = ShardMap.load(a.config)
    print(json.dumps({"virtual_shards": m.virtual_shards, "share": m.share()}, indent=2))
    for url in a.urls:
        print(f"{m.owner(url):8s} {url}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.set_defaults(fn=cmd_export)
    e.add_argument("--corpus", default="output/harvest/harvest_corpus.db")
    e.add_argument("--out", required=True)
    e.add_argument("--machine", required=True)
    e.add_argument("--repo-root", default=".")
    e.add_argument("--limit", type=int)
    v = sub.add_parser("verify")
    v.set_defaults(fn=cmd_verify)
    v.add_argument("bundle")
    i = sub.add_parser("import")
    i.set_defaults(fn=cmd_import)
    i.add_argument("bundle")
    i.add_argument("--store")
    i.add_argument("--index", default=DEFAULT_INDEX)
    i.add_argument("--allow-noncommercial", action="store_true")
    i.add_argument("--allow-unverified", action="store_true",
                   help="also import courses whose license was only declared by a seed, never verified "
                        "on the page (run scripts/harvest_license_audit.py first)")
    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)
    s.add_argument("--index", default=DEFAULT_INDEX)
    h = sub.add_parser("shards")
    h.set_defaults(fn=cmd_shards)
    h.add_argument("urls", nargs="*")
    h.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
