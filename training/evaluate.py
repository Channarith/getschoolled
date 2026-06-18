#!/usr/bin/env python3
"""Evaluate a fine-tuned checkpoint on a held-out JSONL set (offline).

Generates an answer for each eval example and scores it against the reference
with a token-overlap F1 (a transparent, dependency-light proxy). Heavy ML
imports are local so the scoring helper stays unit-testable without torch.

  python training/evaluate.py --base-model /models/education-base \
      --adapter training/out/adapter --eval training/data/eval.jsonl --offline
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Dict, List

_TOKEN = re.compile(r"[a-z0-9]+")


def token_f1(prediction: str, reference: str) -> float:
    pred = _TOKEN.findall(prediction.lower())
    ref = _TOKEN.findall(reference.lower())
    if not pred or not ref:
        return 0.0
    common: Dict[str, int] = {}
    ref_counts: Dict[str, int] = {}
    for t in ref:
        ref_counts[t] = ref_counts.get(t, 0) + 1
    overlap = 0
    for t in pred:
        if ref_counts.get(t, 0) - common.get(t, 0) > 0:
            common[t] = common.get(t, 0) + 1
            overlap += 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(ref)
    return 2 * precision * recall / (precision + recall)


def aggregate_scores(items: List[Dict]) -> Dict:
    """Aggregate per-item scores into overall + per-category + fairness gap.

    items: [{"score": float, "category": str|None, "group": str|None}]
    fairness_gap = max(group mean) - min(group mean) across audience groups
    (0 when fewer than two groups). The bake-off rejects candidates whose gap
    exceeds a threshold (fairness gate).
    """
    scores = [float(i["score"]) for i in items]
    overall = sum(scores) / len(scores) if scores else 0.0

    def _means(key: str) -> Dict[str, float]:
        buckets: Dict[str, List[float]] = {}
        for i in items:
            k = i.get(key)
            if k is None:
                continue
            buckets.setdefault(str(k), []).append(float(i["score"]))
        return {k: sum(v) / len(v) for k, v in buckets.items()}

    by_category = _means("category")
    by_group = _means("group")
    fairness_gap = (max(by_group.values()) - min(by_group.values())) if len(by_group) >= 2 else 0.0
    return {
        "overall": round(overall, 4),
        "by_category": {k: round(v, 4) for k, v in by_category.items()},
        "fairness_gap": round(fairness_gap, 4),
        "n": len(scores),
    }


def read_jsonl(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _prompt(row: Dict) -> str:
    ctx = ", ".join(f"{k}={v}" for k, v in row.get("context", {}).items())
    return f"### Audience:\n{ctx}\n\n### Question:\n{row['instruction']}\n\n### Answer:\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-model", required=True)
    ap.add_argument("--adapter", default="")
    ap.add_argument("--eval", default="training/data/eval.jsonl")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--max-new-tokens", type=int, default=128)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = ap.parse_args(argv)

    if args.offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = (
        args.device
        if args.device != "auto"
        else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    tok = AutoTokenizer.from_pretrained(args.base_model, local_files_only=args.offline)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, local_files_only=args.offline,
        torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
    )
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter)
    model.to(device).eval()

    rows = read_jsonl(args.eval)
    scores: List[float] = []
    for row in rows:
        inputs = tok(_prompt(row), return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        scores.append(token_f1(text, row["response"]))

    mean = sum(scores) / len(scores) if scores else 0.0
    print(json.dumps({"n": len(scores), "token_f1": round(mean, 4)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
