#!/usr/bin/env python3
"""Write the daily list of translated courses the apps can already speak.

  python3 scripts/translation_checkpoint.py
  python3 scripts/translation_checkpoint.py --watch

``--watch`` writes a checkpoint now, then again at each local midnight, so a
long translation run can be listened to in stages.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared.course_translation_library import snapshot_checkpoint  # noqa: E402


def _sleep_until_next_day() -> None:
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
    time.sleep(max(1.0, (tomorrow - now).total_seconds()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch", action="store_true", help="Write again at each local midnight")
    args = parser.parse_args()
    while True:
        manifest = snapshot_checkpoint()
        print(
            f"checkpoint {manifest['day']}: {manifest['files']} course languages "
            f"-> listen in Drive Mode or POST /translate/listen",
            flush=True,
        )
        if not args.watch:
            return
        _sleep_until_next_day()


if __name__ == "__main__":
    main()
