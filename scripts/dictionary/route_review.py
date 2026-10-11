#!/usr/bin/env python3
"""Route staging entries into auto-accept vs human review queue."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import (
        dictionary_dir,
        ensure_layout,
        load_staging,
        route_entries,
        save_review_queue,
        save_staging,
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--language", default="all", help="en|km|all")
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    langs = ("en", "km") if args.language == "all" else (args.language,)
    queued_all = []
    for lang in langs:
        entries = load_staging(root, lang)
        auto, queued = route_entries(entries)
        # Write back statuses
        by_id = {e.id: e for e in auto + queued}
        save_staging(list(by_id.values()), root, lang)
        queued_all.extend(queued)
        print(f"{lang}: auto={len(auto)} queued={len(queued)}")
    save_review_queue(queued_all, root)
    print(f"review_queue={len(queued_all)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
