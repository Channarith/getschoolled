#!/usr/bin/env python3
"""Merge passing CosyVoice channel reports into output/spark/cosyvoice.

The scan root (usually the main checkout output/) is read only. Manifests,
TRAIN_HANDOFF.txt, and census.json are written under --dest.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aoep_shared.cosyvoice_ingest.spark_manifest import build_spark_manifests


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--cosyvoice-repo", type=Path, default=None)
    parser.add_argument("--voices-root", type=Path, default=None)
    args = parser.parse_args(argv)
    census = build_spark_manifests(
        args.scan_root,
        args.dest,
        cosyvoice_repo=args.cosyvoice_repo,
        voices_root=args.voices_root,
    )
    summary = {
        "passing_channels": census["passing_channels"],
        "passing_utterances_reported": census["passing_utterances_reported"],
        "passing_utterances_deduped": census["passing_utterances_deduped"],
        "passing_seconds_deduped": census["passing_seconds_deduped"],
        "exported_channels": census["exported_channels"],
        "exported_utterances_reported": census["exported_utterances_reported"],
        "km_exported": {
            "utterances": census["km_exported"]["utterances"],
            "seconds": census["km_exported"]["seconds"],
            "dropped_duplicate_audio": census["km_exported"]["dropped_duplicate_audio"],
            "recipe": census["km_exported"]["recipe"],
            "train_handoff": census["km_exported"]["train_handoff"],
        },
        "salane": census["salane"],
        "decision": census["decision"],
        "census": str((args.dest / "census.json").resolve()),
    }
    json.dump(summary, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
