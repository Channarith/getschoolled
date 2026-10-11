#!/usr/bin/env python3
"""Shim → CosyVoice synth via train_update --synth (RAG lab)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from theodore_rag_lab.corpus_lab import run_train_update

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", default="en")
    ap.add_argument("--limit", type=int, default=20)  # accepted for compat; lab caps at 20
    args = ap.parse_args(argv)
    report = run_train_update(language=args.language, synth=True)
    print(json.dumps(report.get("synth") or report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
