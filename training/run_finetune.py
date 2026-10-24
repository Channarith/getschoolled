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
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
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
        top = [p for p in PROTECTED if p in r]
        if top:
            problems.append(f"row {i}: protected attribute(s) {top} at the top level")
        tag_leak = [t for t in (r.get("tags") or []) if str(t).lower() in PROTECTED]
        if tag_leak:
            problems.append(f"row {i}: protected attribute(s) {tag_leak} used as tags")
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


def _load_causal_lm(base_model: str, *, offline: bool, device: str, want_4bit: bool):
    """Load the base model. Prefer 4-bit QLoRA; fall back to bf16 LoRA on this GPU."""
    import torch
    from transformers import AutoModelForCausalLM

    if want_4bit:
        try:
            from transformers import BitsAndBytesConfig

            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                local_files_only=offline,
                device_map="auto",
                quantization_config=BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16,
                ),
            )
            print("loaded base in 4-bit QLoRA")
            return model, True
        except Exception as exc:  # noqa: BLE001 — hardware/kernel gaps must not abort the run
            print(
                f"WARNING: 4-bit QLoRA unavailable ({type(exc).__name__}); using bf16 LoRA",
                file=sys.stderr,
            )
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    kwargs: dict = {"local_files_only": offline, "torch_dtype": dtype}
    if device == "cuda":
        kwargs["device_map"] = "auto"
    model = AutoModelForCausalLM.from_pretrained(base_model, **kwargs)
    print(f"loaded base dtype={dtype}")
    return model, False


def train(args, cfg: dict, rows: List[Dict]) -> int:
    if args.offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    # Heavy imports kept local so --check works without them.
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    base_model = args.base_model or cfg.get("base_model")
    device = _detect_device(args.device)
    want_4bit = device == "cuda" and cfg.get("method", "qlora") == "qlora"

    tok = AutoTokenizer.from_pretrained(
        base_model, local_files_only=args.offline, use_fast=True
    )
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    model, used_4bit = _load_causal_lm(
        base_model, offline=args.offline, device=device, want_4bit=want_4bit,
    )

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
    sft_kwargs = dict(
        output_dir=args.output,
        num_train_epochs=float(optim.get("epochs_per_cycle", 1)),
        per_device_train_batch_size=int(optim.get("batch_size", 4)),
        gradient_accumulation_steps=int(optim.get("grad_accum", 4)),
        learning_rate=float(optim.get("lr", 2e-4)),
        logging_steps=10,
        save_strategy="epoch",
        dataset_text_field="text",
        max_length=int(optim.get("max_length", 512)),
        packing=False,
        report_to="none",
        bf16=device == "cuda",
        gradient_checkpointing=device == "cuda",
        optim="adamw_torch",
        dataset_num_proc=1,
    )
    if args.max_steps and args.max_steps > 0:
        sft_kwargs["max_steps"] = args.max_steps
    sft = SFTConfig(**sft_kwargs)
    # trl >= 0.12 names the tokenizer argument processing_class.
    trainer = SFTTrainer(
        model=model, args=sft, train_dataset=ds, peft_config=peft_config,
        processing_class=tok,
    )
    print(f"qlora_4bit={used_4bit}")
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
