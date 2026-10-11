#!/usr/bin/env python3
"""Build progressive read-aloud sentence curriculum from approved staging."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import dictionary_dir, ensure_layout, load_staging
    from aoep_shared.dictionary_curriculum import build_curriculum, save_sentences

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--language", default="en")
    ap.add_argument("--per-difficulty", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    entries = load_staging(root, args.language)
    sentences = build_curriculum(
        entries,
        language=args.language,
        per_difficulty=args.per_difficulty,
        seed=args.seed,
    )
    path = save_sentences(sentences, root, args.language)
    print(f"sentences={len(sentences)} → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
