#!/usr/bin/env python3
"""Keep one metrics layout for both generations of the nightly.

evaluate.py --metrics-dir writes <out>/eval/<who>/<benchmark-stem>.json. The promotion gate and the
frontier-readiness briefing read the older flat names that the Spark has been writing. This copies
the new files to those names so neither breaks, and never overwrites a newer file with an older one.

  eval/<who>/eval.json              -> eval/<who>.json
  eval/<who>/eval_frozen.json       -> eval/<who>.frozen.json
  eval/<who>/eval_frozen_stem.json  -> eval/<who>.stemfrozen.json
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import List

LEGACY = {
    "eval.json": "{who}.json",
    "eval_frozen.json": "{who}.frozen.json",
    "eval_frozen_stem.json": "{who}.stemfrozen.json",
}
WHO = ("base", "stem")


def link_legacy(out: Path) -> List[str]:
    """Copy per-benchmark files to the legacy flat names. Returns the files written."""
    written: List[str] = []
    for who in WHO:
        for source_name, template in LEGACY.items():
            src = out / "eval" / who / source_name
            if not src.is_file():
                continue
            dest = out / "eval" / template.format(who=who)
            if dest.is_file() and dest.stat().st_mtime > src.stat().st_mtime:
                continue
            shutil.copyfile(src, dest)
            written.append(str(dest))
    return written


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    for path in link_legacy(Path(args.out)):
        print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
