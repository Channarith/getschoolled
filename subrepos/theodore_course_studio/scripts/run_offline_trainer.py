#!/usr/bin/env python3
"""Run the offline long-running Theodore Course Studio trainer.

Fully offline: no LLM / no network. Learns a quality model from Good/Better vs
Bad/reject pages, then iteratively assembles and scores courses.

Examples:
  # Overnight on your Mac with the Drive download corpus:
  export THEODORE_COURSE_CORPUS_ROOT=~/Downloads/drive-download-20260807T154004Z-1-001
  export THEODORE_COURSE_STUDIO_DATA=subrepos/theodore_course_studio/data
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py --hours 8

  # Fixed epoch budget (CI / smoke):
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py --epochs 30 --no-scan

  # Resume a previous run:
  python3 subrepos/theodore_course_studio/scripts/run_offline_trainer.py \\
      --resume-run-id offline-abc123 --hours 4 --no-scan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from theodore_course_studio.offline_trainer import run_offline_training  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline long-running course quality trainer (no network)"
    )
    parser.add_argument("--corpus-root", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--epochs", type=int, default=None, help="Max epochs (default 50 if no --hours)")
    parser.add_argument("--hours", type=float, default=None, help="Wall-clock budget")
    parser.add_argument("--target-score", type=float, default=None)
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--fit-passes", type=int, default=2)
    parser.add_argument("--no-scan", action="store_true", help="Skip corpus extract scan")
    parser.add_argument("--resume-run-id", default=None)
    args = parser.parse_args()

    epochs = args.epochs
    if epochs is None and args.hours is None:
        epochs = 50

    state = run_offline_training(
        data_dir=Path(args.data_dir) if args.data_dir else None,
        corpus_root=Path(args.corpus_root) if args.corpus_root else None,
        epochs=epochs,
        hours=args.hours,
        target_score=args.target_score,
        max_docs=args.max_docs,
        run_scan=not args.no_scan,
        resume_run_id=args.resume_run_id,
        fit_passes=args.fit_passes,
    )
    print(json.dumps(state.model_dump(mode="json"), indent=2)[:4000])
    print(
        f"\nrun_id={state.run_id} status={state.status} epochs={state.epoch} "
        f"best_score={state.best_course_score:.4f} best_course={state.best_course_id}"
    )
    print(f"message: {state.message}")
    return 0 if state.status in {"completed", "stopped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
