"""Promote a STEM adapter only when the frozen score rises and no subject hides.

A bake-off that only asks "did we beat the base this cycle?" promotes the same
checkpoint forever, because the ledger starts empty every night. This gate
compares the frozen-exam accuracy to the last promoted frozen accuracy and
rejects a candidate whose weakest adequately-sampled subject is under the floor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional


def subject_min(by_category: Dict[str, float], by_category_n: Dict[str, int], *, min_n: int = 3) -> Optional[float]:
    """Lowest category mean among categories with at least ``min_n`` items."""
    vals = []
    for name, score in (by_category or {}).items():
        if int((by_category_n or {}).get(name, 0)) >= min_n:
            vals.append(float(score))
    if not vals:
        return None
    return round(min(vals), 4)


def decide_promotion(
    *,
    name: str,
    champion: str,
    frozen_accuracy: Optional[float],
    previous_accuracy: Optional[float],
    frozen_subject_min: Optional[float],
    split_subject_min: Optional[float],
    subject_floor: float,
) -> tuple[bool, str]:
    if champion != name:
        return False, "not_champion"
    if frozen_accuracy is None:
        return False, "frozen_eval_required"
    if frozen_subject_min is not None and frozen_subject_min < subject_floor:
        return False, "subject_floor:frozen"
    if split_subject_min is not None and split_subject_min < subject_floor:
        return False, "subject_floor:split"
    if previous_accuracy is not None and float(frozen_accuracy) <= float(previous_accuracy):
        return False, "score_did_not_rise"
    return True, "score_rose"


def _load_metrics(path: str) -> Optional[dict]:
    file = Path(path)
    if not path or not file.is_file():
        return None
    return json.loads(file.read_text(encoding="utf-8"))


def _subject_min_from(metrics: Optional[dict], min_n: int) -> Optional[float]:
    if not metrics:
        return None
    if "subject_min" in metrics and metrics["subject_min"] is not None:
        return float(metrics["subject_min"])
    return subject_min(
        metrics.get("by_category") or {},
        metrics.get("by_category_n") or {},
        min_n=min_n,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default="stem-qlora")
    ap.add_argument("--champion", default="")
    ap.add_argument("--frozen-metrics", required=True)
    ap.add_argument("--split-metrics", default="")
    ap.add_argument("--previous", default="", help="JSON with the last promoted frozen accuracy")
    ap.add_argument("--subject-floor", type=float, default=0.40)
    ap.add_argument("--min-subject-n", type=int, default=3)
    ap.add_argument("--write-promoted", default="", help="write this file when promotion is allowed")
    args = ap.parse_args(argv)

    frozen = _load_metrics(args.frozen_metrics)
    split = _load_metrics(args.split_metrics)
    previous = _load_metrics(args.previous) if args.previous else None
    previous_accuracy = None if not previous else previous.get("accuracy")
    frozen_accuracy = None if not frozen else frozen.get("accuracy")
    allowed, reason = decide_promotion(
        name=args.name,
        champion=args.champion,
        frozen_accuracy=None if frozen_accuracy is None else float(frozen_accuracy),
        previous_accuracy=None if previous_accuracy is None else float(previous_accuracy),
        frozen_subject_min=_subject_min_from(frozen, args.min_subject_n),
        split_subject_min=_subject_min_from(split, args.min_subject_n),
        subject_floor=args.subject_floor,
    )
    payload = {
        "promoted": allowed,
        "reason": reason,
        "champion": args.champion,
        "frozen_accuracy": frozen_accuracy,
        "previous_accuracy": previous_accuracy,
        "subject_floor": args.subject_floor,
    }
    print(json.dumps(payload, indent=2))
    if allowed and args.write_promoted:
        dest = Path(args.write_promoted)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(
                {
                    "name": args.name,
                    "accuracy": frozen_accuracy,
                    "subject_floor": args.subject_floor,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
