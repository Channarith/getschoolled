#!/usr/bin/env python3
"""Shim → clean staging audio via RAG lab train_update (no synth)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from aoep_shared.dictionary_audio import clean_audio_file
    from theodore_rag_lab.corpus_lab import run_train_update

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", default="en")
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.file:
        result = clean_audio_file(args.file, args.out)
        print({
            "ok": result.ok,
            "crisp": str(result.crisp_path) if result.crisp_path else None,
            "snr_db": result.snr_db,
            "reason": result.reason,
        })
        return 0 if result.ok else 1
    report = run_train_update(language=args.language, synth=False)
    print(json.dumps({"audio_clean": report.get("audio_clean"), "root": report.get("root")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
