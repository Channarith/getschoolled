#!/usr/bin/env python3
"""Track A.2/A.3 - pretraining launcher (CPU smoke + cluster launch).

`--check` (CPU, torch-free) loads the size ladder, computes per-rung parameter
counts + Chinchilla token budgets, and validates the 3D-parallelism plan against
WORLD_SIZE - the de-risking step before the real distributed run. Without
`--check` it would hand off to the configured framework (Megatron/NeMo/DeepSpeed/
FSDP) on the cluster; that path executes on GPUs, not in CI.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from model_config import (
    ModelSpec,
    chinchilla_tokens,
    transformer_params,
    validate_parallelism,
)


def plan_from_ladder(ladder_yaml: str, world_size: int, tensor: int, pipeline: int) -> dict:
    import yaml

    cfg = yaml.safe_load(Path(ladder_yaml).read_text(encoding="utf-8"))
    data_parallel = validate_parallelism(world_size, tensor, pipeline)
    rungs = []
    for rung in cfg.get("ladder", []):
        if not all(isinstance(rung.get(k), int) for k in ("layers", "hidden", "heads")):
            # the final 'target' rung may use ${ENV} placeholders; skip in smoke.
            rungs.append({"name": rung.get("name"), "skipped": True})
            continue
        spec = ModelSpec(layers=rung["layers"], hidden=rung["hidden"], heads=rung["heads"])
        params = transformer_params(spec)
        rungs.append({
            "name": rung.get("name"),
            "params": params,
            "params_billions": round(params / 1e9, 2),
            "chinchilla_tokens": chinchilla_tokens(params),
        })
    return {"world_size": world_size, "tensor": tensor, "pipeline": pipeline,
            "data_parallel": data_parallel, "rungs": rungs}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ladder", default="training/scratch/config/model_ladder.yaml")
    ap.add_argument("--world-size", type=int, default=int(os.environ.get("WORLD_SIZE", "8")))
    ap.add_argument("--tensor", type=int, default=8)
    ap.add_argument("--pipeline", type=int, default=1)
    ap.add_argument("--check", action="store_true", help="CPU smoke: plan only, no training")
    args = ap.parse_args(argv)

    plan = plan_from_ladder(args.ladder, args.world_size, args.tensor, args.pipeline)
    if args.check:
        print(json.dumps(plan, indent=2))
        return 0

    raise SystemExit(
        "Real pretraining runs on the GPU cluster via the configured framework; "
        "see training/RUNBOOK.txt. Use --check for the CPU smoke."
    )


if __name__ == "__main__":
    raise SystemExit(main())
