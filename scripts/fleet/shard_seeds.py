#!/usr/bin/env python3
"""Write the seeds that belong to one shard. Sharding is by site (host), deterministic and identical
on every machine, so two machines never crawl the same site.

  shard_seeds.py --seeds seeds.jsonl --shard 0 --of 3 --out /tmp/seeds-0.jsonl
Seed files are JSONL (one {"url": ...} per line, as services/harvester expects) or plain URLs.
Exit 78 (configuration error, not retried by the queue) if the seed file is missing or empty.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402,F401  (stdlib-only import of aoep_shared)
from aoep_shared.fleet_queue import shard_of_url  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--shard", type=int, required=True)
    ap.add_argument("--of", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not os.path.isfile(args.seeds):
        print(f"shard_seeds: seed file {args.seeds} not found. Create it (JSONL of {{\"url\": ..., \"license\": ...}}) "
              "or set HARVEST_SEEDS.", file=sys.stderr)
        return 78
    kept = total = 0
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.seeds, encoding="utf-8") as src, open(args.out, "w", encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            total += 1
            url = line
            if line.startswith("{"):
                try:
                    url = str(json.loads(line).get("url", ""))
                except json.JSONDecodeError:
                    continue
            if url and shard_of_url(url, args.of) == args.shard:
                dst.write(line + "\n")
                kept += 1
    print(f"shard_seeds: shard {args.shard}/{args.of}: kept {kept} of {total} seeds -> {args.out}")
    if total == 0:
        print("shard_seeds: seed file is empty", file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
