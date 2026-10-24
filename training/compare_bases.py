#!/usr/bin/env python3
"""Score every candidate base model on the benchmarks and write a leaderboard.

One command replaces the runbook's shell loop:

  python3 training/compare_bases.py --machine spark            # every model whose weights are present
  python3 training/compare_bases.py --machine ibuypower --only qwen3-4b,gemma-3-4b-it
  python3 training/compare_bases.py --list                      # what fits where; downloads nothing

Each candidate runs evaluate.py in its own process group with a timeout (no orphans), once per
model load, over all benchmarks. Missing weights are reported as "missing", never an error.
Outputs: output/spark/eval/bases/<name>/*.json, leaderboard.json and leaderboard.txt.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# (usable accelerator memory in GB, label). Spark is unified memory; iBuyPower is VRAM.
MACHINES = {"spark": 121 - 16, "ibuypower": 8}
OVERHEAD_GB = 4.0


def qlora_gb(params_b: float) -> float:
    """Rough QLoRA training memory: 4-bit weights + LoRA/optimizer/activations at batch 1."""
    return round(params_b * 0.55 + OVERHEAD_GB, 1)


def bf16_eval_gb(params_b: float) -> float:
    return round(params_b * 2.0 + 2.0, 1)


def eval_4bit_gb(params_b: float) -> float:
    return round(params_b * 0.6 + 1.5, 1)


def fits(params_b: float, machine: str) -> Dict[str, bool]:
    budget = MACHINES[machine]
    return {
        "qlora": qlora_gb(params_b) <= budget,
        "eval_bf16": bf16_eval_gb(params_b) <= budget,
        "eval_4bit": eval_4bit_gb(params_b) <= budget,
    }


def load_candidates(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _read(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_candidate(py: str, model_dir: Path, benchmarks: List[str], out_dir: Path, *,
                  device: str, max_new_tokens: int, timeout_s: int, load_4bit: bool = False) -> Dict:
    cmd = [py, str(ROOT / "training" / "evaluate.py"), "--offline", "--device", device,
           "--base-model", str(model_dir), "--max-new-tokens", str(max_new_tokens),
           "--metrics-dir", str(out_dir)]
    if load_4bit:
        cmd.append("--load-4bit")
    cmd += ["--eval", *[str(ROOT / b) for b in benchmarks]]
    # Own process group so a timeout or Ctrl-C kills the model process and its children.
    proc = subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        output, _ = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
        return {"status": "timeout"}
    except KeyboardInterrupt:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait()
        raise
    if proc.returncode != 0:
        return {"status": "failed", "returncode": proc.returncode, "tail": (output or "")[-400:]}
    return {"status": "ok"}


def summarize(name: str, out_dir: Path, benchmarks: List[str]) -> Dict:
    row: Dict = {"name": name}
    frozen = _read(out_dir / "eval_frozen.json") or {}
    behaviour = _read(out_dir / "eval_behavior_v1.json") or {}
    multi = _read(out_dir / "eval_multilingual_v1.json") or {}
    row["frozen_f1"] = frozen.get("accuracy")
    row["fairness_gap"] = frozen.get("fairness_gap")
    merged: Dict[str, float] = {}
    for blob in (frozen, behaviour, multi):
        merged.update(blob.get("behaviour") or {})
    row["abstain"] = merged.get("abstain")
    row["grounded"] = merged.get("grounded")
    row["hint"] = merged.get("hint")
    row["refuse"] = merged.get("refuse")
    row["spoken"] = merged.get("spoken")
    row["language"] = merged.get("language")
    row["multilingual_f1"] = multi.get("accuracy")
    row["by_language_f1"] = multi.get("by_language") or {}
    return row


def score(row: Dict) -> float:
    """One sortable number: mean of what was measured. A tie-break aid, not a verdict."""
    keys = ["frozen_f1", "abstain", "grounded", "hint", "refuse", "spoken", "language", "multilingual_f1"]
    vals = [row[k] for k in keys if isinstance(row.get(k), (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def render(rows: List[Dict], floors: Dict[str, float]) -> str:
    cols = ["frozen_f1", "abstain", "grounded", "hint", "refuse", "spoken", "language", "multilingual_f1"]
    lines = [f"{'MODEL':<26} {'SCORE':>6} " + " ".join(f"{c[:9]:>9}" for c in cols) + "  NOTES"]
    for row in rows:
        cells = " ".join(f"{row[c]:>9.3f}" if isinstance(row.get(c), (int, float)) else f"{'-':>9}" for c in cols)
        notes = []
        for key, floor in floors.items():
            if isinstance(row.get(key), (int, float)) and row[key] < floor:
                notes.append(f"below {key} floor {floor}")
        if row.get("status") not in (None, "ok"):
            notes.append(row["status"])
        lines.append(f"{row['name']:<26} {row.get('score', 0):>6.3f} {cells}  {'; '.join(notes)}")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(ROOT / "training" / "config" / "base_candidates.yaml"))
    ap.add_argument("--machine", default="spark", choices=sorted(MACHINES))
    ap.add_argument("--weights", default=str(ROOT / "models" / "weights"))
    ap.add_argument("--out", default=str(ROOT / "output" / "spark" / "eval" / "bases"))
    ap.add_argument("--only", default="", help="comma-separated candidate names")
    ap.add_argument("--device", default="cuda", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--max-new-tokens", type=int, default=96)
    ap.add_argument("--timeout-min", type=int, default=90, help="per candidate")
    ap.add_argument("--list", action="store_true", help="print what fits on this machine and exit")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args(argv)

    cfg = load_candidates(Path(args.config))
    candidates = cfg.get("candidates", [])
    only = {s for s in args.only.split(",") if s}
    if only:
        candidates = [c for c in candidates if c["name"] in only]
    benchmarks = cfg.get("benchmarks", [])
    floors = cfg.get("floors", {})
    weights = Path(args.weights)

    if args.list:
        print(f"{'MODEL':<26} {'PARAMS':>7} {'QLoRA GB':>9} {'bf16 GB':>8} fits QLoRA / eval on {args.machine}  weights present")
        for c in candidates:
            f = fits(c["params_b"], args.machine)
            present = (weights / c["dir"]).is_dir()
            print(f"{c['name']:<26} {c['params_b']:>6.1f}B {qlora_gb(c['params_b']):>9} {bf16_eval_gb(c['params_b']):>8} "
                  f"{'yes' if f['qlora'] else 'no':>8} / {'bf16' if f['eval_bf16'] else ('4bit' if f['eval_4bit'] else 'no'):<8} {'yes' if present else 'no'}")
        return 0

    out_root = Path(args.out)
    rows: List[Dict] = []
    for c in candidates:
        model_dir = weights / c["dir"]
        if not model_dir.is_dir():
            rows.append({"name": c["name"], "status": "missing", "score": 0.0})
            continue
        fit = fits(c["params_b"], args.machine)
        if not fit["eval_bf16"] and not fit["eval_4bit"]:
            rows.append({"name": c["name"], "status": f"too big for {args.machine}", "score": 0.0})
            continue
        out_dir = out_root / c["name"]
        print(f"== scoring {c['name']} ==", flush=True)
        result = run_candidate(args.python, model_dir, benchmarks, out_dir, device=args.device,
                               max_new_tokens=args.max_new_tokens, timeout_s=args.timeout_min * 60,
                               load_4bit=not fit["eval_bf16"])
        row = summarize(c["name"], out_dir, benchmarks)
        row["status"] = result["status"]
        row["score"] = score(row) if result["status"] == "ok" else 0.0
        rows.append(row)

    rows.sort(key=lambda r: r.get("score", 0.0), reverse=True)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "leaderboard.json").write_text(json.dumps({"machine": args.machine, "floors": floors, "rows": rows},
                                                          indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    table = render(rows, floors)
    (out_root / "leaderboard.txt").write_text(table + "\n", encoding="utf-8")
    print(table)
    return 0 if any(r.get("status") == "ok" for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
