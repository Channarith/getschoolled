#!/usr/bin/env python3
"""Build the training scenario catalog (400+ situations)."""

from __future__ import annotations

import argparse
import sys

from aoep_shared.training_agents.catalog import reload_catalog
from aoep_shared.training_agents.catalog_builder import write_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description="Build scenario_catalog.json")
    parser.add_argument("--out", default="", help="Output path (default: package data/)")
    args = parser.parse_args()

    from pathlib import Path

    path = Path(args.out) if args.out else None
    payload = write_catalog(path)
    reload_catalog()
    print(f"Wrote {payload['count']} scenarios across {len(payload['domains'])} domains")
    for domain, n in sorted(payload["domains"].items(), key=lambda x: -x[1]):
        print(f"  {domain}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
