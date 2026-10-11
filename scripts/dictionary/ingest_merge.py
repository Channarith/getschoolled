#!/usr/bin/env python3
"""Async-friendly merge of dictionary baselines into staging JSONL."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


async def _merge_async(baseline_dir: Path, root: Path) -> dict:
    from aoep_shared.dictionary_corpus import (
        ensure_layout,
        ingest_from_baseline_dir,
        load_staging,
        merge_entries,
        save_staging,
    )

    ensure_layout(root)
    fresh = await asyncio.to_thread(ingest_from_baseline_dir, baseline_dir)

    # Preserve human review decisions from existing staging.
    preserved = {}
    for lang in ("en", "km"):
        for e in load_staging(root, lang):
            if e.review_status in ("approved", "rejected"):
                preserved[(lang, e.id)] = e

    by_lang: dict[str, list] = {"en": [], "km": []}
    for e in fresh:
        by_lang.setdefault(e.language, []).append(e)

    stats = {}
    for lang, rows in by_lang.items():
        merged = merge_entries(rows + [
            preserved[k] for k in preserved if k[0] == lang
        ])
        # Re-apply preserved statuses
        for e in merged:
            key = (lang, e.id)
            if key in preserved:
                e.review_status = preserved[key].review_status
                if preserved[key].gloss_en:
                    e.gloss_en = preserved[key].gloss_en
                if preserved[key].inflections:
                    e.inflections = dict(preserved[key].inflections)
        save_staging(merged, root, lang)
        stats[lang] = len(merged)
    return stats


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import dictionary_dir, ensure_layout

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--baselines", type=Path, default=None)
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    baseline_dir = args.baselines or (root / "baselines")
    if not baseline_dir.is_dir():
        print(f"missing baselines dir: {baseline_dir}", file=sys.stderr)
        print("run: python3 scripts/dictionary/fetch_baselines.py --from-fixtures", file=sys.stderr)
        return 1

    stats = asyncio.run(_merge_async(baseline_dir, root))
    for lang, n in stats.items():
        print(f"staging[{lang}]={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
