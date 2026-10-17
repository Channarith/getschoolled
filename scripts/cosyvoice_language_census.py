#!/usr/bin/env python3
"""Print a per-language CosyVoice census against the 100-utterance / 20-minute floor.

Reads channel recipes under --scan-root (default: output). Does not download,
merge, or restart ingest. Merged trees are skipped so mirrored copies count once.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "packages" / "shared" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from aoep_shared.cosyvoice_ingest.census import format_census, language_census  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", type=Path, default=Path("output"))
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")
    args = parser.parse_args(argv)
    rows = language_census(args.scan_root)
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_census(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
