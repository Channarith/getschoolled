#!/usr/bin/env python3
"""Scheduled data-retention purge runner (cron / k8s CronJob).

Calls the memory service's retention endpoint to delete data past its retention
window. Stdlib only. Configure MEMORY_URL (default http://localhost:8004).

  python3 scripts/retention_purge.py
  MEMORY_URL=https://memory.internal python3 scripts/retention_purge.py --default-days 180
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--memory-url", default=os.environ.get("MEMORY_URL", "http://localhost:8004"))
    ap.add_argument("--default-days", type=int, default=None,
                    help="fallback retention for records without retention_days")
    args = ap.parse_args(argv)

    body = json.dumps({"default_retention_days": args.default_days}).encode()
    req = urllib.request.Request(
        args.memory_url.rstrip("/") + "/retention/purge", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        report = json.loads(resp.read())
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
