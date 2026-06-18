#!/usr/bin/env python3
"""Track A.3 - pretraining orchestration (proxy ladder -> full run).

Sequences the run: cheap proxy rungs first, fit the scaling law, then the full
target run with checkpoint/resume + monitoring. `--check` prints the staged plan
(with a predicted target loss when proxy losses are supplied) without launching;
the real multi-day run executes on the cluster (training/scratch/pretrain/RUNBOOK.txt).
"""

from __future__ import annotations

import argparse
import json
from typing import Dict, List, Optional, Sequence, Tuple

from run_pretrain import plan_from_ladder
from scaling import fit_power_law, predict_loss


def build_plan(ladder_yaml: str, world_size: int, tensor: int, pipeline: int, *,
               proxy_points: Optional[Sequence[Tuple[float, float]]] = None,
               checkpoint_interval: int = 1000) -> Dict:
    base = plan_from_ladder(ladder_yaml, world_size, tensor, pipeline)
    stages: List[Dict] = []
    for rung in base["rungs"]:
        stages.append({
            "stage": rung["name"],
            "kind": "proxy" if rung.get("name", "").startswith(("proxy", "mid")) else "full",
            "params_billions": rung.get("params_billions"),
            "tokens": rung.get("chinchilla_tokens"),
            "checkpoint_interval": checkpoint_interval,
            "skipped": rung.get("skipped", False),
        })
    plan = {**base, "stages": stages}
    if proxy_points and len(proxy_points) >= 2:
        fit = fit_power_law(proxy_points)
        # Predict loss at the largest non-skipped rung's token budget as a proxy
        # for target compute.
        target_tokens = max((s["tokens"] for s in stages if s.get("tokens")), default=None)
        plan["scaling_fit"] = {"a": round(fit["a"], 4), "b": round(fit["b"], 4)}
        if target_tokens:
            plan["predicted_target_loss"] = round(predict_loss(fit, target_tokens), 4)
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ladder", default="training/scratch/config/model_ladder.yaml")
    ap.add_argument("--world-size", type=int, default=8)
    ap.add_argument("--tensor", type=int, default=8)
    ap.add_argument("--pipeline", type=int, default=1)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    plan = build_plan(args.ladder, args.world_size, args.tensor, args.pipeline)
    if args.check:
        print(json.dumps(plan, indent=2))
        return 0
    raise SystemExit("Full pretraining runs on the cluster; see RUNBOOK.txt. Use --check.")


if __name__ == "__main__":
    raise SystemExit(main())
