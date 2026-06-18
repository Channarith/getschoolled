#!/usr/bin/env python3
"""Model bake-off / champion-challenger harness.

Scores candidate models on the same eval metrics and picks the champion via the
OptimizationLedger (non-regressing promotion). Used to compare Track A (from
scratch) vs Track B (open-weight base + adapters); the champion is what the
served LLMProvider points at, and any candidate can be reverted.

Pure/offline (metrics are supplied, e.g. from training/evaluate.py); testable.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from aoep_shared.optimization import OptimizationLedger


@dataclass
class Candidate:
    name: str
    metrics: Dict[str, float]


def run_bakeoff(
    candidates: Sequence[Candidate],
    *,
    primary: str = "accuracy",
    higher_is_better: bool = True,
) -> dict:
    """Return the champion candidate and the populated ledger."""
    ledger = OptimizationLedger(primary_metric=primary, higher_is_better=higher_is_better)
    for c in candidates:
        step = ledger.commit("model", {"name": c.name}, c.metrics)
        ledger.promote_if_better(step)
    champ = ledger.champion("model")
    return {
        "champion": champ.params["name"] if champ else None,
        "primary": primary,
        "score": champ.metrics.get(primary) if champ else None,
        "candidates": [{"name": c.name, **c.metrics} for c in candidates],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", required=True,
                    help="JSON file: [{\"name\":..., \"metrics\":{...}}, ...]")
    ap.add_argument("--primary", default="accuracy")
    ap.add_argument("--lower-is-better", action="store_true")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    cands = [Candidate(d["name"], d.get("metrics", {})) for d in data]
    result = run_bakeoff(cands, primary=args.primary,
                         higher_is_better=not args.lower_is_better)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
