#!/usr/bin/env python3
"""Track A.4 - alignment: SFT -> preference optimization (DPO) + safety gate.

Repo-side logic + a torch-free `--check`: builds/validates SFT examples and DPO
preference pairs and runs the fairness guardrail + a safety blocklist over the
data before any GPU run. The real SFT/DPO/RLHF executes on the cluster
(training/scratch/pretrain/RUNBOOK.txt); this reuses training/pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # training/ on path
from pipeline.dataset import assert_no_protected  # noqa: E402

# Minimal safety blocklist for the red-team gate (extend on the cluster).
UNSAFE_MARKERS = ("build a bomb", "synthesize a nerve agent", "make a weapon",
                  "credit card numbers", "child sexual")


def is_safe(text: str) -> bool:
    low = text.lower()
    return not any(m in low for m in UNSAFE_MARKERS)


def build_preference_pairs(prefs: Sequence[Dict]) -> List[Dict]:
    """Validate DPO triples {prompt, chosen, rejected}.

    Drops pairs whose chosen response is unsafe or where chosen == rejected, and
    enforces the protected-attribute guardrail on any provided context.
    """
    pairs: List[Dict] = []
    for p in prefs:
        assert_no_protected(p.get("context", {}))
        chosen, rejected = p.get("chosen", ""), p.get("rejected", "")
        if not chosen or chosen == rejected:
            continue
        if not is_safe(chosen):
            continue
        pairs.append({"prompt": p["prompt"], "chosen": chosen, "rejected": rejected})
    return pairs


def build_sft_examples(rows: Sequence[Dict]) -> List[Dict]:
    out: List[Dict] = []
    for r in rows:
        assert_no_protected(r.get("context", {}))
        if r.get("instruction") and r.get("response") and is_safe(r["response"]):
            out.append({"instruction": r["instruction"], "response": r["response"]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sft", default=None, help="JSONL of SFT rows")
    ap.add_argument("--prefs", default=None, help="JSONL of DPO preference triples")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    def _load(p):
        return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]

    sft = build_sft_examples(_load(args.sft)) if args.sft else []
    pairs = build_preference_pairs(_load(args.prefs)) if args.prefs else []
    summary = {"sft_examples": len(sft), "dpo_pairs": len(pairs)}
    if args.check:
        print(json.dumps(summary))
        return 0
    raise SystemExit("Real SFT/DPO runs on the GPU cluster; see RUNBOOK.txt. Use --check.")


if __name__ == "__main__":
    raise SystemExit(main())
