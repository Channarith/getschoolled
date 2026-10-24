#!/usr/bin/env python3
"""Build the bake-off candidates from the per-benchmark eval files and run the bake-off.

Reads  <out>/eval/base/*.json and <out>/eval/stem/*.json (from evaluate.py --metrics-dir),
writes <out>/bakeoff/candidates.json, result.json and floors.args.

The adapter may only win if it scores higher on the frozen set AND does not regress on tutor
behaviour: its abstain / refuse / hint accuracy must be at least the base model's. A model that
gains word overlap by guessing instead of abstaining, or by giving away answers, is rejected.

Optionally scores the live llama-server as a third candidate; a failure there never aborts.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BEHAVIOUR_FLOORS = ("abstain", "refuse", "hint")


def _read(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def collect_metrics(eval_dir: Path) -> Dict[str, float]:
    """Flatten the per-benchmark files into one metrics dict."""
    frozen = _read(eval_dir / "eval_frozen.json") or _read(eval_dir / "eval.json") or {}
    behaviour = _read(eval_dir / "eval_behavior_v1.json") or {}
    multi = _read(eval_dir / "eval_multilingual_v1.json") or {}
    if not frozen and not behaviour:
        raise SystemExit(f"no eval results under {eval_dir}")
    metrics: Dict[str, float] = {
        "accuracy": float(frozen.get("accuracy", behaviour.get("accuracy", 0.0))),
        "token_f1": float(frozen.get("token_f1", frozen.get("accuracy", 0.0))),
        "fairness_gap": float(frozen.get("fairness_gap") or 0.0),
    }
    for blob in (frozen, behaviour, multi):  # later files win: the behaviour file is the authority
        for key, value in (blob.get("behaviour") or {}).items():
            metrics[key] = float(value)
    if multi.get("accuracy") is not None:
        metrics["multilingual_f1"] = float(multi["accuracy"])
    # The weakest sampled subject on the frozen exam: one weak subject sets the floor.
    if frozen.get("subject_min") is not None:
        metrics["subject_min"] = float(frozen["subject_min"])
    return metrics


def build_candidates(out: Path) -> list[dict]:
    return [
        {"name": "qwen-base", "track": "B", "metrics": collect_metrics(out / "eval" / "base")},
        {"name": "stem-qlora", "track": "B", "metrics": collect_metrics(out / "eval" / "stem")},
    ]


def floors_from_base(candidates: list[dict]) -> Dict[str, float]:
    base = next(c for c in candidates if c["name"] == "qwen-base")["metrics"]
    return {k: round(base[k], 4) for k in BEHAVIOUR_FLOORS if k in base}


def add_serving(out: Path, candidates: list[dict], url: str, model: str, eval_path: Path) -> None:
    if not url or not eval_path.is_file():
        return
    metrics_path = out / "eval" / "serving.json"
    cmd = [sys.executable, str(Path(__file__).parent / "spark_serve_eval.py"), "--base-url", url,
           "--model", model, "--eval", str(eval_path), "--metrics-out", str(metrics_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, start_new_session=True)
    except (subprocess.TimeoutExpired, OSError):
        print("WARNING: serving-model eval timed out; bake-off continues without it", file=sys.stderr)
        return
    if proc.returncode != 0:
        print("WARNING: serving-model eval failed; bake-off continues without it", file=sys.stderr)
        return
    data = _read(metrics_path) or {}
    candidates.append({"name": "serving-qwen", "track": "serving", "metrics": {
        "accuracy": float(data["accuracy"]), "fairness_gap": float(data.get("fairness_gap") or 0.0),
        "token_f1": float(data.get("token_f1") or data["accuracy"])}})


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--serve-url", default="")
    ap.add_argument("--serve-model", default="")
    ap.add_argument("--max-fairness-gap", type=float, default=0.1)
    ap.add_argument("--min-subject-score", type=float, default=None,
                    help="reject an adapter whose weakest sampled subject is under this (default off)")
    ap.add_argument("--note-only", action="store_true", help="write candidate.json for a non-winning adapter")
    args = ap.parse_args(argv)
    out = Path(args.out)
    (out / "bakeoff").mkdir(parents=True, exist_ok=True)

    if args.note_only:
        result = _read(out / "bakeoff" / "result.json") or {}
        note = {"promoted": False, "candidate": "stem-qlora", "adapter": str(out / "adapters" / "stem"),
                "champion": result.get("champion"), "rejected": result.get("rejected", []),
                "reason": "promote only when the adapter wins the fairness- and behaviour-gated bake-off"}
        (out / "candidate.json").write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(note))
        return 0

    from bakeoff import Candidate, run_bakeoff
    from eval_layout import link_legacy

    link_legacy(out)
    candidates = build_candidates(out)
    add_serving(out, candidates, args.serve_url, args.serve_model, out / "data" / "eval.jsonl")
    floors = floors_from_base(candidates)
    (out / "bakeoff" / "candidates.json").write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
    args_line = [f"--min-metric {k}={v}" for k, v in floors.items()]
    if args.min_subject_score is not None:
        args_line.append(f"--min-subject-score {args.min_subject_score}")
    (out / "bakeoff" / "floors.args").write_text(" ".join(args_line) + "\n", encoding="utf-8")
    result = run_bakeoff([Candidate(c["name"], c["metrics"]) for c in candidates], primary="accuracy",
                         max_fairness_gap=args.max_fairness_gap, min_metrics=floors,
                         min_subject_score=args.min_subject_score)
    (out / "bakeoff" / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
