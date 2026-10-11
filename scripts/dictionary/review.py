#!/usr/bin/env python3
"""Shim → Theodore RAG lab corpus review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lab_shim import ensure_paths  # noqa: E402

ensure_paths()


def main(argv: list[str] | None = None) -> int:
    from theodore_rag_lab.corpus_lab import apply_review, list_review

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["list", "confirm", "correct", "reject", "audio-rejected"])
    ap.add_argument("--id", default="")
    ap.add_argument("--gloss", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args(argv)
    if args.action == "list":
        print(json.dumps(list_review(limit=args.limit), indent=2, ensure_ascii=False))
        return 0
    if args.action == "audio-rejected":
        from aoep_shared.dictionary_corpus import dictionary_dir, load_staging

        n = 0
        for lang in ("en", "km"):
            for e in load_staging(dictionary_dir(), lang):
                for slot in (e.audio or {}).values():
                    q = getattr(slot, "quality", None)
                    if q == "rejected":
                        print(f"{e.id}\t{lang}\t{e.lemma}")
                        n += 1
        print(f"count={n}")
        return 0
    if not args.id:
        print("--id required", file=sys.stderr)
        return 2
    print(json.dumps(
        apply_review(
            entry_id=args.id,
            action=args.action,
            gloss_en=args.gloss,
            note=args.note,
        ),
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
