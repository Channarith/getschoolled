#!/usr/bin/env python3
"""Convert CosyVoice ingest output to a Fish-Speech-style layout and a generic JSONL manifest.

  python3 scripts/voice_dataset_convert.py output/cosyvoice_km_easykhmer output/cosyvoice_yue_hktv \\
      --out data/voice/km_yue_v1
  python3 scripts/voice_dataset_convert.py output --out data/voice/all --audio copy      # for rsync
  python3 scripts/voice_dataset_convert.py output --out data/voice/ship --only-licensed   # shippable only

Each input is a directory that has (or contains) OUTPUT/04_cosyvoice/train/wav.scp.
The input is never modified. Outputs under --out:
  manifest.jsonl  train.jsonl  val.jsonl   one clip per line: path, text, lang, speaker, split,
                                          duration, snr, source_url and a provenance block
  fish/<train|val>/<speaker>/<utt>.wav + <utt>.lab        Fish Speech folder layout
  rejected.jsonl                                           why each dropped clip was dropped
  provenance.json / provenance.txt                         sources, licence status, hours

PROVENANCE RULE: sources are third-party YouTube channels with no confirmed license or
consent. A clip is ship_ok only when its source is listed in urls/licensed_sources.txt.
--only-licensed keeps just those, so unlicensed audio cannot end up in anything that ships.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
from aoep_shared.voice_dataset import Filters, convert, render_provenance  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--allowlist", type=Path, default=ROOT / "urls" / "licensed_sources.txt")
    ap.add_argument("--only-licensed", action="store_true", help="keep only clips whose source is in the allowlist")
    ap.add_argument("--audio", choices=["link", "copy", "none"], default="link",
                    help="how fish/ gets its wav files: symlink (default), copy (use before rsync), or none")
    ap.add_argument("--min-seconds", type=float, default=1.0)
    ap.add_argument("--max-seconds", type=float, default=20.0)
    ap.add_argument("--min-snr", type=float, default=8.0, help="dB; clips with a recorded SNR below this are dropped")
    ap.add_argument("--min-asr-confidence", type=float, default=None)
    ap.add_argument("--dedupe-audio", action="store_true", help="also drop byte-identical audio (reads every file)")
    ap.add_argument("--require-duration", action="store_true")
    ap.add_argument("--val-fraction", type=float, default=0.05)
    args = ap.parse_args()
    flt = Filters(
        min_seconds=args.min_seconds, max_seconds=args.max_seconds, min_snr_db=args.min_snr,
        min_asr_confidence=args.min_asr_confidence, dedupe_audio=args.dedupe_audio,
        only_licensed=args.only_licensed, require_duration=args.require_duration, val_fraction=args.val_fraction,
    )
    report = convert(args.inputs, args.out, flt, args.allowlist, args.audio)
    print(render_provenance(report))
    print(f"seen {report['clips_seen']} clips from {len(report['inputs'])} folder(s); wrote {args.out}")
    for note in report["split_notes"]:
        print("note:", note)
    if not report["clips_ship_ok"]:
        print("WARNING: no clip is allowlisted, so none of this data may ship (internal experiments only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
