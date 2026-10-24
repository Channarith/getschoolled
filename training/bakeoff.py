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
from typing import Dict, Sequence

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
    max_fairness_gap: float | None = None,
    min_subject_score: float | None = None,
    min_metrics: Dict[str, float] | None = None,
) -> dict:
    """Score candidates on the same metrics and pick the champion.

    Candidates whose ``fairness_gap`` metric exceeds ``max_fairness_gap`` are
    rejected by the fairness gate before championing (never promoted). Each
    eligible candidate is recorded as an OptimizationStep; the best non-
    regressing one wins.
    """
    eligible: list[Candidate] = []
    rejected: list[dict] = []
    for c in candidates:
        gap = float(c.metrics.get("fairness_gap", 0.0))
        weakest = c.metrics.get("subject_min")
        if max_fairness_gap is not None and gap > max_fairness_gap:
            rejected.append({"name": c.name, "fairness_gap": gap, "reason": "fairness_gate"})
            continue
        # One weak subject sets the floor: a high average cannot hide a subject under it.
        if (
            min_subject_score is not None
            and weakest is not None
            and float(weakest) < min_subject_score
        ):
            rejected.append({
                "name": c.name,
                "subject_min": float(weakest),
                "reason": "subject_floor",
            })
            continue
        # Behaviour floors (e.g. abstain >= 0.8): a candidate that scores higher word overlap by
        # guessing instead of abstaining, or by revealing hints, must not win. A metric that was
        # not measured does not fail the gate.
        failed = {
            name: c.metrics[name]
            for name, floor in (min_metrics or {}).items()
            if name in c.metrics and float(c.metrics[name]) < float(floor)
        }
        if failed:
            rejected.append({"name": c.name, "metrics": failed, "reason": "metric_floor"})
            continue
        eligible.append(c)

    ledger = OptimizationLedger(primary_metric=primary, higher_is_better=higher_is_better)
    for c in eligible:
        step = ledger.commit("model", {"name": c.name}, c.metrics)
        ledger.promote_if_better(step)
    champ = ledger.champion("model")
    return {
        "champion": champ.params["name"] if champ else None,
        "primary": primary,
        "score": champ.metrics.get(primary) if champ else None,
        "champion_metrics": dict(champ.metrics) if champ else {},
        "rejected": rejected,
        "candidates": [{"name": c.name, **c.metrics} for c in candidates],
    }


def promote_champion(result: dict, champion_path: str) -> dict:
    """Persist the bake-off winner as the served champion pointer."""
    from champion import ChampionRegistry

    if not result.get("champion"):
        return {"promoted": None}
    reg = ChampionRegistry(champion_path)
    reg.promote(result["champion"], result.get("champion_metrics", {}))
    return {"promoted": result["champion"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", required=True,
                    help="JSON file: [{\"name\":..., \"metrics\":{...}}, ...]")
    ap.add_argument("--primary", default="accuracy")
    ap.add_argument("--lower-is-better", action="store_true")
    ap.add_argument("--max-fairness-gap", type=float, default=None)
    ap.add_argument("--min-subject-score", type=float, default=None)
    ap.add_argument("--min-metric", action="append", default=[], metavar="NAME=FLOOR",
                    help="reject candidates below a floor, e.g. --min-metric abstain=0.8 (repeatable)")
    ap.add_argument("--champion-path", default=None,
                    help="if set, persist the winner as the served champion pointer")
    args = ap.parse_args(argv)

    data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    cands = [Candidate(d["name"], d.get("metrics", {})) for d in data]
    floors: Dict[str, float] = {}
    for spec in args.min_metric:
        name, _, value = spec.partition("=")
        floors[name.strip()] = float(value)
    result = run_bakeoff(cands, primary=args.primary,
                         higher_is_better=not args.lower_is_better,
                         max_fairness_gap=args.max_fairness_gap,
                         min_subject_score=args.min_subject_score,
                         min_metrics=floors or None)
    if args.champion_path:
        result.update(promote_champion(result, args.champion_path))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
