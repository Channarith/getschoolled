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
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scoring import score_behaviour, token_f1  # noqa: E402,F401  (token_f1 re-exported)


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
    by_category_n: Dict[str, int] = {}
    for i in items:
        key = i.get("category")
        if key is None:
            continue
        name = str(key)
        by_category_n[name] = by_category_n.get(name, 0) + 1
    fairness_gap = (max(by_group.values()) - min(by_group.values())) if len(by_group) >= 2 else 0.0
    return {
        "overall": round(overall, 4),
        "by_category": {k: round(v, 4) for k, v in by_category.items()},
        "by_category_n": by_category_n,
        "fairness_gap": round(fairness_gap, 4),
        "n": len(scores),
    }


def read_jsonl(path: str) -> List[Dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(f"WARNING: skipping malformed JSONL line: {exc}", file=sys.stderr)
    return rows


def _prompt(row: Dict) -> str:
    ctx = ", ".join(f"{k}={v}" for k, v in row.get("context", {}).items())
    instruction = row.get("instruction", "")
    return f"### Audience:\n{ctx}\n\n### Question:\n{instruction}\n\n### Answer:\n"


def _group(row: Dict) -> str | None:
    """Audience group for the fairness gap. Pedagogical fields only."""
    ctx = row.get("context") or {}
    level = ctx.get("reading_level")
    if level:
        return str(level)
    language = ctx.get("language")
    return str(language) if language else None


def _category(row: Dict) -> str | None:
    tags = row.get("tags") or []
    return str(tags[0]) if tags else None


def _effective_scorer(row: Dict) -> Optional[str]:
    """An explicit scorer wins; the frozen set's tags map to behaviour scorers
    (abstain items must decline, recall items must not), so it needs no edits."""
    if row.get("scorer"):
        return str(row["scorer"])
    tags = row.get("tags") or []
    if "abstain" in tags:
        return "abstain"
    if "recall" in tags:
        return "grounded"
    return None


def run_eval(
    rows: List[Dict],
    generate: Callable[[str], str],
    *,
    eval_path: str = "",
    adapter: str = "",
    truth_log: str = "",
) -> Dict:
    """Score every row with `generate(prompt) -> text`. Pure: no torch needed.

    Always reports token_f1 (the bake-off primary, unchanged). Rows that carry a
    `scorer` also feed a per-behaviour accuracy (abstain, grounded, hint, refuse,
    spoken, language) so promotion can gate on behaviour, not word overlap alone.

    With ``eval_path`` set, each overlap-scored answer also gets truth-curve fields
    (groundedness, abstention) and, with ``truth_log``, a row appended to that JSONL;
    the summary then carries the weakest-subject score the promotion gate needs.
    """
    items: List[Dict] = []
    behaviour: Dict[str, List[float]] = {}
    by_lang: Dict[str, List[float]] = {}
    skipped = 0
    for row in rows:
        reference = row.get("response", "")
        scorer = _effective_scorer(row)
        if not reference and not scorer:
            print("WARNING: skipping row without 'response' or 'scorer'", file=sys.stderr)
            skipped += 1
            continue
        text = generate(_prompt(row))
        if reference:
            lang = str((row.get("context") or {}).get("language") or "en")
            # English keeps the original tokenizer so frozen-exam scores stay comparable over time.
            f1 = token_f1(text, reference, legacy_ascii=(lang == "en"))
            item = {"score": f1, "category": _category(row), "group": _group(row)}
            if eval_path:
                from truth_curve import append_truth_row, exam_fields, truth_fields

                fields = truth_fields(text, row)
                fields.update(exam_fields(eval_path, adapter))
                fields["score"] = f1
                fields["group"] = item["group"]
                if not fields.get("category"):
                    fields["category"] = item["category"]
                item = fields
                if truth_log:
                    append_truth_row(truth_log, fields)
            items.append(item)
            by_lang.setdefault(lang, []).append(f1)
        got = score_behaviour({**row, "scorer": scorer}, text) if scorer else None
        if got is not None:
            behaviour.setdefault(str(scorer), []).append(got)
    if not items and not behaviour:
        return {"n": 0, "token_f1": 0.0, "accuracy": 0.0, "fairness_gap": 0.0,
                "by_category": {}, "behaviour": {}, "by_language": {}, "skipped": skipped}
    agg = (
        aggregate_scores(items)
        if items
        else {"overall": 0.0, "by_category": {}, "by_category_n": {}, "fairness_gap": 0.0, "n": 0}
    )
    out = {
        "n": agg["n"] + sum(len(v) for v in behaviour.values() if not items),
        "token_f1": agg["overall"],
        "accuracy": agg["overall"],  # bake-off primary: token-overlap F1, unchanged
        "fairness_gap": agg["fairness_gap"],
        "by_category": agg["by_category"],
        "by_category_n": agg["by_category_n"],
        "behaviour": {k: round(sum(v) / len(v), 4) for k, v in sorted(behaviour.items())},
        "behaviour_n": {k: len(v) for k, v in sorted(behaviour.items())},
        "by_language": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_lang.items())},
        "skipped": skipped,
    }
    if eval_path and items:
        from promotion_gate import subject_min

        grounded = [float(i["groundedness"]) for i in items if "groundedness" in i]
        abstain = [1.0 if i.get("abstain_correct") else 0.0 for i in items if "abstain_correct" in i]
        out["subject_min"] = subject_min(agg["by_category"], agg["by_category_n"])
        out["groundedness"] = round(sum(grounded) / len(grounded), 4) if grounded else None
        out["abstain_accuracy"] = round(sum(abstain) / len(abstain), 4) if abstain else None
    if behaviour:
        # Behaviour-only files (hint, refuse, spoken, abstain) have no overlap target.
        out["behaviour_mean"] = round(sum(out["behaviour"].values()) / len(out["behaviour"]), 4)
        if not items:
            out["accuracy"] = out["behaviour_mean"]
    return out


def _load_generator(args) -> Callable[[str], str]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = (
        args.device
        if args.device != "auto"
        else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    tok = AutoTokenizer.from_pretrained(args.base_model, local_files_only=args.offline)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    if args.load_4bit and device == "cuda":
        # Small GPUs (the 8 GB iBuyPower): load 4-bit so a 4B-7B model can be scored at all.
        from transformers import BitsAndBytesConfig

        model = AutoModelForCausalLM.from_pretrained(
            args.base_model, local_files_only=args.offline, device_map="auto",
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                   bnb_4bit_compute_dtype=torch.bfloat16),
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.base_model, local_files_only=args.offline,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
        )
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter)
    if not args.load_4bit:
        model.to(device)
    model.eval()

    def generate(prompt: str) -> str:
        inputs = tok(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            out = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=tok.pad_token_id,
            )
        return tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    return generate


def _write(path: str, summary: Dict) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: Optional[list] = None, generator: Optional[Callable[[str], str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-model", required=generator is None)
    ap.add_argument("--adapter", default="")
    ap.add_argument("--eval", nargs="+", default=["training/data/eval.jsonl"],
                    help="one or more JSONL files; the model is loaded once")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--max-new-tokens", type=int, default=128)
    ap.add_argument("--load-4bit", action="store_true", help="load the base in 4-bit (small GPUs)")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--metrics-out", default="", help="write metrics JSON here (single --eval file)")
    ap.add_argument("--metrics-dir", default="",
                    help="write <eval-file-stem>.json per --eval file here (use with several files)")
    ap.add_argument("--truth-log", default="", help="append groundedness and abstention rows (JSONL)")
    args = ap.parse_args(argv)

    if len(args.eval) > 1 and args.metrics_out:
        print("ERROR: --metrics-out takes one --eval file; use --metrics-dir for several", file=sys.stderr)
        return 2

    batches = []
    for path in args.eval:
        rows = read_jsonl(path)
        if not rows:
            print(f"ERROR: eval file is empty: {path}", file=sys.stderr)
            return 1
        batches.append((path, rows))

    if args.offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    generate = generator or _load_generator(args)
    status = 0
    for path, rows in batches:
        summary = run_eval(rows, generate, eval_path=path, adapter=args.adapter, truth_log=args.truth_log)
        if summary["n"] == 0:
            print(f"ERROR: nothing scored in {path}", file=sys.stderr)
            status = 1
            continue
        summary["eval_file"] = os.path.basename(path)
        target = args.metrics_out if len(args.eval) == 1 else ""
        if not target and args.metrics_dir:
            target = str(Path(args.metrics_dir) / (Path(path).stem + ".json"))
        if target:
            _write(target, summary)
        print(json.dumps(summary, ensure_ascii=False))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
