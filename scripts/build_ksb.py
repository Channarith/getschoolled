#!/usr/bin/env python3
"""Load, validate and report the KSB occupational standards for corporate courses.

Each corporate course has a KSB definition in scripts/ksb/data/<course>.json,
modelled on the UK apprenticeship standard format (duties mapped to Knowledge,
Skills and Behaviours). This tool loads them into NumPy structured arrays via
scripts/ksb/framework.py, validates the duty<->KSB cross references, and prints
a summary. Optionally it persists each standard as a NumPy .npz archive.

Usage:
  python3 scripts/build_ksb.py                 # summary + validation for all
  python3 scripts/build_ksb.py --course ai-ml-fellowship   # full detail
  python3 scripts/build_ksb.py --save build/ksb            # write .npz archives
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ksb.framework import KSBStandard, load_all  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course", help="show full detail for one course_id")
    parser.add_argument("--save", metavar="DIR", help="write <course>.npz to DIR")
    parser.add_argument(
        "--data-dir",
        default=str(Path(__file__).resolve().parent.parent / "sample-curriculum"),
        help="curriculum directory containing <course>/ksb.json files",
    )
    args = parser.parse_args(argv)

    standards = load_all(args.data_dir)
    if not standards:
        print(f"No KSB data found in {args.data_dir}", file=sys.stderr)
        return 1

    if args.course:
        std = standards.get(args.course)
        if std is None:
            print(f"Unknown course: {args.course}", file=sys.stderr)
            print(f"Available: {', '.join(sorted(standards))}", file=sys.stderr)
            return 1
        print(std.describe())
        problems = std.validate()
        print("\nValidation: " + ("OK" if not problems else f"{len(problems)} issue(s)"))
        for p in problems:
            print(f"  - {p}")
        return 0 if not problems else 2

    total_problems = 0
    print(f"KSB standards in {args.data_dir}\n")
    header = f"{'course_id':32} {'duties':>6} {'K':>4} {'S':>4} {'B':>4}  status"
    print(header)
    print("-" * len(header))
    for cid in sorted(standards):
        std = standards[cid]
        problems = std.validate()
        total_problems += len(problems)
        status = "OK" if not problems else f"{len(problems)} issue(s)"
        print(
            f"{cid:32} {len(std.duties):>6} {len(std.knowledge):>4} "
            f"{len(std.skills):>4} {len(std.behaviours):>4}  {status}"
        )
        for p in problems:
            print(f"    - {p}")

    if args.save:
        out_dir = Path(args.save)
        out_dir.mkdir(parents=True, exist_ok=True)
        for cid, std in standards.items():
            std.to_npz(out_dir / f"{cid}.npz")
        print(f"\nWrote {len(standards)} .npz archives to {out_dir}")

    print(
        f"\n{len(standards)} course(s), "
        f"{'all valid' if total_problems == 0 else f'{total_problems} total issue(s)'}"
    )
    return 0 if total_problems == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
