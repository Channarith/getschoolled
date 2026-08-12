#!/usr/bin/env python3
"""Run a corpus training scan from the CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from theodore_course_studio.training_run import run_training_pass  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Theodore Course Studio training run")
    parser.add_argument("--corpus-root", default=None)
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--no-extract", action="store_true")
    parser.add_argument("--no-seed-hints", action="store_true")
    args = parser.parse_args()
    report = run_training_pass(
        corpus_root=Path(args.corpus_root) if args.corpus_root else None,
        max_docs=args.max_docs,
        extract_text=not args.no_extract,
        seed_page_hints=not args.no_seed_hints,
    )
    print(json.dumps(report.model_dump(mode="json"), indent=2))
    print(
        f"\nScanned {report.documents_scanned} · "
        f"incorporate {len(report.incorporate_ids)} · "
        f"reject {len(report.reject_ids)} · "
        f"review queue {len(report.review_queue_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
