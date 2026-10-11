#!/usr/bin/env python3
"""Continuous train-and-update loop for the dictionary + voice corpus.

Idempotent: re-seeds baselines when fingerprints change, merges, routes review,
applies feedback, rebuilds sentences, optionally synthesizes + cleans audio.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICT = ROOT / "scripts" / "dictionary"


def _run(script: str, args: list[str]) -> int:
    cmd = [sys.executable, str(DICT / script), *args]
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_corpus import (
        dictionary_dir,
        ensure_layout,
        fingerprint_baselines,
        read_fingerprint,
        write_fingerprint,
    )
    from aoep_shared.dictionary_feedback import DictionaryFeedbackStore

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--force", action="store_true", help="Re-fetch fixtures even if fingerprint matches")
    ap.add_argument("--synth", action="store_true", help="Call CosyVoice synth (requires COSYVOICE_URL)")
    ap.add_argument("--ship-packs", action="store_true")
    ap.add_argument("--language", default="en")
    args = ap.parse_args(argv)

    root = ensure_layout(args.root or dictionary_dir())
    root_args = ["--root", str(root)]

    baseline_dir = root / "baselines"
    fp = fingerprint_baselines(baseline_dir) if baseline_dir.is_dir() else ""
    prev = read_fingerprint(root)
    if args.force or not fp or fp != prev or not any(baseline_dir.glob("*")):
        rc = _run("fetch_baselines.py", root_args + ["--from-fixtures"])
        if rc != 0:
            return rc
        fp = fingerprint_baselines(root / "baselines")
        write_fingerprint(root, fp)
    else:
        print(f"baselines unchanged ({fp[:12]}…)")

    for script, extra in (
        ("ingest_merge.py", []),
        ("route_review.py", []),
    ):
        rc = _run(script, root_args + extra)
        if rc != 0:
            return rc

    store = DictionaryFeedbackStore(root / "review" / "feedback.json")
    for lang in ("en", "km"):
        n = store.apply_to_staging(lang, root)
        if n:
            print(f"feedback applied[{lang}]={n}")

    rc = _run("build_sentences.py", root_args + ["--language", args.language])
    if rc != 0:
        return rc

    export_args = root_args[:]
    if args.ship_packs:
        export_args.append("--ship")
    rc = _run("export_packs.py", export_args)
    if rc != 0:
        return rc

    if args.synth:
        _run("synthesize_audio.py", root_args + ["--language", args.language, "--limit", "20"])
        _run("clean_audio.py", root_args + ["--language", args.language])
    else:
        # Still clean any existing raw clips
        _run("clean_audio.py", root_args + ["--language", args.language])

    print("train_update complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
