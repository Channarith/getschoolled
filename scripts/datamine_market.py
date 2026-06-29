#!/usr/bin/env python3
"""Datamine market/ROI reference points into ``market`` content packs.

Modes:
  --seed                 Emit the curated, attributed seed as a pack (offline).
  --from-file PATH       Extract $ amounts / percentages from a local file
                         (a downloaded report/HTML/txt) into a pack (offline).
  --url URL              Fetch a page and extract numbers (REQUIRES network
                         egress; fails gracefully with guidance if blocked).
  --list                 Print the current merged market references + meta.

Common options for extraction: --source, --reference, --region, --year, --out.
Output packs land in an AOEP_CONTENT_PACKS root (default
~/.cache/aoep/content-packs/market) so aoep_shared.market_intel merges them.

Live web scraping is intentionally network-gated and never fabricates data; if
egress is disabled it tells you how to enable it instead of inventing numbers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aoep_shared.harvest.market_bridge import (
    default_market_packs_dir,
    extract_market_numbers,
    write_market_pack,
)
from aoep_shared.market_intel import _SEED, meta, search_references


def _emit_seed(out: Path) -> int:
    import json

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"pack": "curated_seed", "description": "Curated attributed seed",
                    "records": _SEED}, indent=2),
        encoding="utf-8",
    )
    return len(_SEED)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--from-file", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("--list", action="store_true", dest="do_list")
    ap.add_argument("--source", default="datamine")
    ap.add_argument("--reference", default="datamined")
    ap.add_argument("--region", default="global")
    ap.add_argument("--year", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    packs_dir = default_market_packs_dir()

    if args.do_list:
        m = meta()
        print(f"Market references: {m['count']} ({m['builtin']} seed + {m['from_packs']} packs) "
              f"across {m['regions']} regions, {m['sources']} sources")
        for r in search_references(limit=200):
            print(f"  [{r.region:<7}] {r.metric:<26} {r.value:>16,.0f} {r.unit:<16} "
                  f"({r.source}, {r.year})")
        print(f"\nNOTE: {m['disclaimer']}")
        return 0

    if args.seed:
        out = Path(args.out) if args.out else (packs_dir / "curated_seed.json")
        n = _emit_seed(out)
        print(f"Wrote {n} curated seed references -> {out}")
        return 0

    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8", errors="ignore")
        records = extract_market_numbers(
            text, source=args.source, reference=args.reference,
            region=args.region, default_year=args.year)
        out = Path(args.out) if args.out else (packs_dir / "from_file.json")
        n = write_market_pack(records, out, pack_name="from_file")
        print(f"Extracted + wrote {n} candidate references -> {out}")
        print("Review/verify each before investor use.")
        return 0

    if args.url:
        import urllib.request

        try:
            req = urllib.request.Request(args.url, headers={"User-Agent": "AOEP-datamine/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001 - network is often restricted here
            print(f"Fetch failed: {exc}", file=sys.stderr)
            print("Live datamining needs outbound network egress. Enable the target "
                  "host in Cloud Agent -> Network Access, or use --from-file on a "
                  "locally downloaded report.", file=sys.stderr)
            return 2
        records = extract_market_numbers(
            text, source=args.source, reference=args.reference or args.url,
            region=args.region, default_year=args.year)
        out = Path(args.out) if args.out else (packs_dir / "from_url.json")
        n = write_market_pack(records, out, pack_name="from_url")
        print(f"Extracted + wrote {n} candidate references -> {out}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
