#!/usr/bin/env python3
"""Noise-filter / QC pipeline: raw → crisp (or rejected)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
    from aoep_shared.dictionary_audio import clean_audio_file, clean_entry_audio
    from aoep_shared.dictionary_corpus import (
        dictionary_dir,
        ensure_layout,
        load_staging,
        save_staging,
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--language", default="en")
    ap.add_argument("--file", type=Path, default=None, help="Clean a single WAV/MP3 path")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.file:
        result = clean_audio_file(args.file, args.out)
        print({
            "ok": result.ok,
            "crisp": str(result.crisp_path) if result.crisp_path else None,
            "snr_db": result.snr_db,
            "duration_sec": result.duration_sec,
            "reason": result.reason,
        })
        return 0 if result.ok else 1

    root = ensure_layout(args.root or dictionary_dir())
    entries = load_staging(root, args.language)
    crisp = rejected = missing = 0
    updated = []
    for e in entries:
        slot = (e.audio or {}).get(args.language)
        raw = getattr(slot, "raw", None) if slot else None
        if not raw:
            missing += 1
            updated.append(e)
            continue
        row = clean_entry_audio(e, language=args.language, root=root)
        q = row.audio[args.language].quality
        if q == "crisp":
            crisp += 1
        elif q == "rejected":
            rejected += 1
        updated.append(row)
    save_staging(updated, root, args.language)
    print({"crisp": crisp, "rejected": rejected, "missing_raw": missing, "total": len(entries)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
