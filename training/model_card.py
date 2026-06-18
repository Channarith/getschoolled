#!/usr/bin/env python3
"""Generate a model card (JSON) - transparency about a served/candidate model.

Builds a model card from bake-off / evaluation metrics (accuracy, per-category,
fairness gap) plus intended-use and limitations text. Used by the Trust layer's
public model-cards page. Pure/offline; JSON (no new markdown, per convention).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional


def build_model_card(
    name: str,
    metrics: Dict,
    *,
    intended_use: str = "Educational tutoring and lesson delivery.",
    limitations: Optional[List[str]] = None,
    training_data: str = "Permissively-licensed/OER course materials + curated instruction data.",
    base_model: Optional[str] = None,
) -> Dict:
    return {
        "name": name,
        "base_model": base_model,
        "created_at": time.time(),
        "metrics": {
            "accuracy": metrics.get("accuracy"),
            "by_category": metrics.get("by_category", {}),
            "fairness_gap": metrics.get("fairness_gap"),
        },
        "intended_use": intended_use,
        "training_data": training_data,
        "limitations": limitations or [
            "May produce ungrounded answers; mitigated by the hallucination guard.",
            "Probabilistic; use the human-in-the-loop review for high-stakes content.",
        ],
        "fairness": "Protected attributes (race, ethnicity) are excluded from training context.",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", required=True)
    ap.add_argument("--metrics", required=True, help="JSON file with accuracy/by_category/fairness_gap")
    ap.add_argument("--base-model", default=None)
    ap.add_argument("--out", required=True, help="output JSON path")
    args = ap.parse_args(argv)

    metrics = json.loads(Path(args.metrics).read_text(encoding="utf-8"))
    card = build_model_card(args.name, metrics, base_model=args.base_model)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(out), "name": card["name"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
