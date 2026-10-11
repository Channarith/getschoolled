#!/usr/bin/env python3
"""CLI to list / accept / correct / reject queued dictionary entries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import (
        dictionary_dir,
        ensure_layout,
        load_review_queue,
        load_staging,
        save_review_queue,
        save_staging,
    )
    from aoep_shared.dictionary_feedback import DictionaryFeedbackStore

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("action", choices=["list", "confirm", "correct", "reject", "audio-rejected"])
    ap.add_argument("--id", default="", help="entry id")
    ap.add_argument("--gloss", default="", help="corrected gloss_en")
    ap.add_argument("--note", default="")
    ap.add_argument("--inflection", action="append", default=[], help="key=value")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    store = DictionaryFeedbackStore(root / "review" / "feedback.json")

    if args.action == "list":
        rows = load_review_queue(root)[: max(1, args.limit)]
        for e in rows:
            print(f"{e.id}\t{e.language}\t{e.kind}\t{e.lemma}\t{e.gloss_en[:60]}\t{e.notes}")
        print(f"count={len(rows)}")
        return 0

    if args.action == "audio-rejected":
        n = 0
        for lang in ("en", "km"):
            for e in load_staging(root, lang):
                for slot in (e.audio or {}).values():
                    q = slot.quality if hasattr(slot, "quality") else (slot or {}).get("quality")
                    if q == "rejected":
                        print(f"{e.id}\t{lang}\t{e.lemma}\t{e.notes}")
                        n += 1
        print(f"count={n}")
        return 0

    if not args.id:
        print("--id required", file=sys.stderr)
        return 2

    infl = {}
    for item in args.inflection:
        if "=" in item:
            k, v = item.split("=", 1)
            infl[k.strip()] = v.strip()

    # Find entry language
    found = None
    lang = "en"
    for cand in ("en", "km"):
        for e in load_staging(root, cand):
            if e.id == args.id:
                found = e
                lang = cand
                break
        if found:
            break
    if not found:
        print(f"entry not found: {args.id}", file=sys.stderr)
        return 1

    action = args.action
    gloss = args.gloss or found.gloss_en
    store.record(
        entry_id=found.id,
        lemma=found.lemma,
        action=action,
        gloss_en=gloss,
        language=lang,
        inflections=infl,
        note=args.note,
    )
    applied = store.apply_to_staging(lang, root)
    # Refresh queue
    queued = [e for e in load_staging(root, lang) if e.review_status == "queued"]
    # Merge with other language queue
    other = "km" if lang == "en" else "en"
    queued += [e for e in load_staging(root, other) if e.review_status == "queued"]
    save_review_queue(queued, root)
    print(json.dumps({"ok": True, "action": action, "id": args.id, "staging_updates": applied}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
