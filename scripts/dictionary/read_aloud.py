#!/usr/bin/env python3
"""CLI read-aloud trainer: one sentence at a time, score pronunciation/enunciation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import dictionary_dir, ensure_layout
    from aoep_shared.dictionary_curriculum import next_read_aloud, score_read_aloud

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--language", default="en")
    ap.add_argument("--learner", default="local")
    ap.add_argument("--heard", default="", help="Non-interactive: score this transcript")
    ap.add_argument("--once", action="store_true", help="Print one prompt and exit")
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    prompt = next_read_aloud(
        language=args.language,
        learner_id=args.learner,
        root=root,
    )
    if prompt.get("error"):
        print(json.dumps(prompt, indent=2))
        return 1

    print(f"[{prompt['difficulty']}] {prompt['sentence']}")
    forms = [t["form"] for t in prompt.get("targets") or []]
    if forms:
        print("focus:", ", ".join(forms))
    for tip in prompt.get("mouth_tips") or []:
        print("mouth:", tip)

    if args.once and not args.heard:
        print(json.dumps({"session_id": prompt["session_id"], "sentence": prompt["sentence"]}))
        return 0

    heard = args.heard
    if not heard and sys.stdin.isatty():
        try:
            heard = input("heard> ").strip()
        except EOFError:
            heard = ""
    if not heard:
        print("no transcript; pass --heard or type at the prompt", file=sys.stderr)
        return 2

    result = score_read_aloud(
        sentence=prompt["sentence"],
        heard=heard,
        target_forms=forms,
        learner_id=args.learner,
        language=args.language,
        root=root,
    )
    print(json.dumps({
        "score": result["score"],
        "stars": result["stars"],
        "feedback": result["feedback"],
        "missed_forms": result["missed_forms"],
        "difficulty": result["difficulty"],
        "weak": result["weak"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
