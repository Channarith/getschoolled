#!/usr/bin/env python3
"""Run the training-data quality gate over a sessions JSON file.

  python3 training/quality_gate.py --in output/spark/data/sessions.json \
      --out output/spark/data/sessions.clean.json --report output/spark/data/quality.json

Exit codes: 0 ok, 3 hard failure (protected attribute leaked), 4 too little data survived.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline.quality import run_gate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", nargs="+", required=True, help="one or more sessions JSON files (merged)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default="")
    ap.add_argument("--no-scrub", action="store_true", help="drop sessions with personal data instead of scrubbing")
    ap.add_argument("--min-keep", type=float, default=0.5, help="fail if less than this share survives")
    ap.add_argument("--min-sessions", type=int, default=1)
    ap.add_argument("--seed", type=int, default=17, help="deterministic shuffle so the eval split mixes every behaviour")
    args = ap.parse_args(argv)

    sessions: list = []
    for path in args.inp:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            print(f"ERROR: sessions file must be a JSON list: {path}", file=sys.stderr)
            return 2
        sessions.extend(data)
    clean, report = run_gate(sessions, scrub=not args.no_scrub)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "hard"}, ensure_ascii=False))
    if report["hard"]:
        for line in report["hard"][:10]:
            print(f"HARD FAILURE: {line}", file=sys.stderr)
        return 3
    keep = len(clean) / max(1, len(sessions))
    if len(clean) < args.min_sessions or keep < args.min_keep:
        print(f"ERROR: only {len(clean)}/{len(sessions)} sessions passed the gate (need {args.min_keep:.0%})", file=sys.stderr)
        return 4
    random.Random(args.seed).shuffle(clean)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(clean)} clean sessions -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
