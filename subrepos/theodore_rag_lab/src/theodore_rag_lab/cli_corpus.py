"""CLI entrypoints for dictionary corpus ops (Theodore RAG lab)."""

from __future__ import annotations

import argparse
import json
import sys


def corpus_update_main(argv: list[str] | None = None) -> int:
    from .corpus_lab import run_train_update

    ap = argparse.ArgumentParser(description="Dictionary corpus train-update (RAG lab)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--synth", action="store_true")
    ap.add_argument("--ship-packs", action="store_true")
    ap.add_argument("--language", default="en")
    args = ap.parse_args(argv)
    report = run_train_update(
        force=args.force,
        language=args.language,
        synth=args.synth,
        ship_packs=args.ship_packs,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


def read_aloud_main(argv: list[str] | None = None) -> int:
    from .read_aloud_lab import read_aloud_next, read_aloud_score

    ap = argparse.ArgumentParser(description="Read-aloud trainer (RAG lab)")
    ap.add_argument("--language", default="en")
    ap.add_argument("--learner", default="local")
    ap.add_argument("--heard", default="")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv)
    prompt = read_aloud_next(language=args.language, learner_id=args.learner)
    if prompt.get("error"):
        print(json.dumps(prompt, indent=2))
        return 1
    print(f"[{prompt.get('difficulty')}] {prompt.get('sentence')}")
    forms = [t["form"] for t in prompt.get("targets") or []]
    if args.once and not args.heard:
        return 0
    heard = args.heard
    if not heard and sys.stdin.isatty():
        try:
            heard = input("heard> ").strip()
        except EOFError:
            heard = ""
    if not heard:
        print("pass --heard or type at the prompt", file=sys.stderr)
        return 2
    result = read_aloud_score(
        sentence=prompt["sentence"],
        heard=heard,
        target_forms=forms,
        language=args.language,
        learner_id=args.learner,
    )
    print(json.dumps({
        "score": result["score"],
        "feedback": result["feedback"],
        "missed_forms": result.get("missed_forms"),
        "difficulty": result.get("difficulty"),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(corpus_update_main())
