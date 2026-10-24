#!/usr/bin/env python3
"""Time NLLB translation on a fixed set of sentences: one-by-one versus batched, CPU versus CUDA.

  python3 scripts/nllb_bench.py --device cuda --n 64 --target km
  python3 scripts/nllb_bench.py --device cpu  --n 16 --target km     # CPU on the Spark needs --allow-cpu

Run each device in its own process (the model is cached per process). Prints one JSON line.
The numbers are only meaningful on the real machine; nothing here is a benchmark claim.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

SENTENCES = [
    "Welcome to the course. Today we will learn how fractions describe parts of a whole.",
    "A triangle has three sides and three angles. The angles always add up to one hundred eighty degrees.",
    "Plants make their own food using sunlight, water and carbon dioxide.",
    "Please read the passage carefully and then answer the questions that follow.",
    "The capital of a country is the city where its government meets.",
    "To add two numbers, count up from the larger one.",
    "What do you think will happen next in the story? Explain your reasoning.",
    "Remember to check your work before you move on to the next problem.",
]


def fixed_sentences(n: int) -> list[str]:
    return [f"{SENTENCES[i % len(SENTENCES)]} ({i // len(SENTENCES) + 1})" for i in range(n)]


def run(device: str, n: int, source: str, target: str, batch: int, beams: int, allow_cpu: bool, translate=None) -> dict:
    from aoep_shared import devices, nllb

    if device in ("cpu", "cuda"):
        os.environ["NLLB_DEVICE"] = device
    if device == "cpu":
        if devices.require_cuda() and not allow_cpu:
            raise SystemExit("this host requires CUDA: pass --allow-cpu to time the CPU on purpose")
        if allow_cpu:
            os.environ["AOEP_ALLOW_CPU"] = "1"

    do = translate or nllb.translate_batch
    texts = fixed_sentences(n)
    do(texts[:2], source=source, target=target, batch_size=2, num_beams=beams)  # load + warm up, not timed
    t0 = time.perf_counter()
    for t in texts:
        do([t], source=source, target=target, batch_size=1, num_beams=beams)
    single = time.perf_counter() - t0
    t0 = time.perf_counter()
    out = do(texts, source=source, target=target, batch_size=batch, num_beams=beams)
    batched = time.perf_counter() - t0
    status = nllb.nllb_status()
    return {
        "device": status.get("device"),
        "sentences": n,
        "batch_size": batch,
        "num_beams": beams,
        "one_by_one_s": round(single, 2),
        "batched_s": round(batched, 2),
        "sentences_per_s_batched": round(n / batched, 2) if batched else None,
        "speedup_batched_vs_one_by_one": round(single / batched, 2) if batched else None,
        "sample": out[0][:80] if out else "",
        "gpu_free_mb": status.get("gpu_free_mb"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--source", default="en")
    ap.add_argument("--target", default="km")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--beams", type=int, default=4)
    ap.add_argument("--allow-cpu", action="store_true", help="needed to time CPU on a host that requires CUDA")
    args = ap.parse_args(argv)
    result = run(args.device, args.n, args.source, args.target, args.batch, args.beams, args.allow_cpu)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
