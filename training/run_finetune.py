#!/usr/bin/env python3
"""Offline QLoRA/LoRA fine-tune for the education LLM (Linux/Ubuntu).

Runs fully offline (no network): pass a LOCAL base-model directory and
``--offline`` and it sets HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE. On a CUDA GPU it
uses 4-bit QLoRA (bitsandbytes); without CUDA it falls back to a plain LoRA
fine-tune on CPU/fp32 (slow, but works for smoke tests).

The heavy ML imports (torch/transformers/peft/trl) happen INSIDE train(), so the
``--check`` path validates the config + dataset (and the fairness guardrail)
without importing them - usable on any machine, and what CI exercises.

Examples:
  # validate everything, no GPU/torch needed:
  python training/run_finetune.py --check \
      --config training/config/finetune.yaml --train training/data/train.jsonl

  # real offline run against a local base model:
  python training/run_finetune.py --offline \
      --base-model /models/education-base \
      --config training/config/finetune.yaml \
      --train training/data/train.jsonl --output training/out/adapter
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

PROTECTED = ("race", "ethnicity")


def load_yaml(path: str) -> dict:
    import yaml  # lightweight, always available

    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def read_jsonl(path: str) -> List[Dict]:
    rows: List[Dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def validate_dataset(rows: List[Dict]) -> List[str]:
    """Return a list of problems; empty means the dataset is valid."""
    problems: List[str] = []
    if not rows:
        problems.append("dataset is empty")
    for i, r in enumerate(rows):
        if "instruction" not in r or "response" not in r:
            problems.append(f"row {i}: missing instruction/response")
        ctx = r.get("context", {})
        leaked = [p for p in PROTECTED if p in ctx]
        if leaked:
            problems.append(f"row {i}: protected attribute(s) {leaked} in context")
    return problems


def format_example(row: Dict) -> str:
    ctx = row.get("context", {})
    ctx_str = ", ".join(f"{k}={v}" for k, v in ctx.items())
    return (
        f"### Audience:\n{ctx_str}\n\n"
        f"### Question:\n{row['instruction']}\n\n"
        f"### Answer:\n{row['response']}"
    )


def _plan(cfg: dict, rows: List[Dict], base_model: str, device: str) -> str:
    lora = cfg.get("lora", {})
    return (
        f"base_model={base_model or cfg.get('base_model')} method={cfg.get('method')}\n"
        f"device={device} examples={len(rows)} "
        f"lora_r={lora.get('r')} epochs={cfg.get('optim', {}).get('epochs_per_cycle')}"
    )


def _detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch  # noqa: PLC0415

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def train(args, cfg: dict, rows: List[Dict]) -> int:
    if args.offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    # Heavy imports kept local so --check works without them.
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    base_model = args.base_model or cfg.get("base_model")
    device = _detect_device(args.device)
    use_4bit = device == "cuda" and cfg.get("method", "qlora") == "qlora"

    tok = AutoTokenizer.from_pretrained(
        base_model, local_files_only=args.offline, use_fast=True
    )
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model_kwargs: dict = {"local_files_only": args.offline}
    if use_4bit:
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        model_kwargs["device_map"] = "auto"
    else:
        model_kwargs["torch_dtype"] = (
            torch.bfloat16 if device == "cuda" else torch.float32
        )

    model = AutoModelForCausalLM.from_pretrained(base_model, **model_kwargs)

    lcfg = cfg.get("lora", {})
    peft_config = LoraConfig(
        r=int(lcfg.get("r", 16)),
        lora_alpha=int(lcfg.get("alpha", 32)),
        lora_dropout=float(lcfg.get("dropout", 0.05)),
        target_modules=lcfg.get("target_modules", ["q_proj", "v_proj"]),
        task_type="CAUSAL_LM",
    )

    ds = Dataset.from_list([{"text": format_example(r)} for r in rows])
    optim = cfg.get("optim", {})
    sft = SFTConfig(
        output_dir=args.output,
        num_train_epochs=float(optim.get("epochs_per_cycle", 1)),
        per_device_train_batch_size=int(optim.get("batch_size", 4)),
        gradient_accumulation_steps=int(optim.get("grad_accum", 4)),
        learning_rate=float(optim.get("lr", 2e-4)),
        max_steps=args.max_steps,
        logging_steps=5,
        save_strategy="epoch",
        dataset_text_field="text",
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model, args=sft, train_dataset=ds, peft_config=peft_config,
        tokenizer=tok,
    )
    trainer.train()
    trainer.save_model(args.output)
    tok.save_pretrained(args.output)
    print(f"saved fine-tuned adapter to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="training/config/finetune.yaml")
    ap.add_argument("--train", default="training/data/train.jsonl")
    ap.add_argument("--base-model", default="", help="local path or HF id")
    ap.add_argument("--output", default="training/out/adapter")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--offline", action="store_true", help="no network (HF offline)")
    ap.add_argument("--check", action="store_true", help="validate only; no training")
    args = ap.parse_args(argv)

    cfg = load_yaml(args.config)
    rows = read_jsonl(args.train)
    problems = validate_dataset(rows)
    device = _detect_device(args.device)

    print("=== fine-tune plan ===")
    print(_plan(cfg, rows, args.base_model, device))
    if problems:
        print("dataset problems:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    if args.check:
        print("--check: dataset + config valid; no training performed.")
        return 0

    if not (args.base_model or cfg.get("base_model")):
        print("no base model configured (set --base-model)", file=sys.stderr)
        return 2
    return train(args, cfg, rows)


if __name__ == "__main__":
    raise SystemExit(main())
