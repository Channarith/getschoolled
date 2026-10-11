#!/usr/bin/env python3
"""Video → CosyVoice training ingest CLI.

Operator-supplied YouTube/Vimeo URL list (or local media dir) → denoise →
segment → ASR → CosyVoice Kaldi-style recipe under OUTPUT/04_cosyvoice/.

Examples:
  python3 scripts/cosyvoice_ingest.py \\
    --urls-file urls.txt --language en --output-dir output/cosyvoice_en

  python3 scripts/cosyvoice_ingest.py \\
    --media-dir ./clips --language km --output-dir output/cosyvoice_km \\
    --skip-download

  python3 scripts/cosyvoice_ingest.py --help

Env: COSYVOICE_REPO, COSYVOICE_INGEST_ROOT, AOEP_ASR_MODEL / WHISPER_MODEL,
YT_DLP_BIN, AOEP_ASR_DEVICE, AOEP_ASR_COMPUTE_TYPE.

Respect copyright/terms: only download URLs you are allowed to use; this tool
does not scrape or ship third-party corpora.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "packages" / "shared" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--urls-file",
        type=Path,
        default=None,
        help="Text file: one YouTube/Vimeo URL per line (# comments ok)",
    )
    ap.add_argument(
        "--media-dir",
        type=Path,
        default=None,
        help="Local audio/video directory (skips network when used with --skip-download)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Pipeline root (default: COSYVOICE_INGEST_ROOT or output/cosyvoice_ingest)",
    )
    ap.add_argument("--language", default="en", help="BCP-47 / Whisper language code")
    ap.add_argument(
        "--speaker",
        default="auto",
        help="Speaker id for utt2spk (default: auto = one spk per source media)",
    )
    ap.add_argument("--instruct", default="", help="Optional CosyVoice instruct text per utt")
    ap.add_argument("--split-name", default="train", help="Recipe split folder name")
    ap.add_argument("--min-utt-sec", type=float, default=1.0)
    ap.add_argument("--max-utt-sec", type=float, default=12.0)
    ap.add_argument("--silence-db", type=float, default=-40.0)
    ap.add_argument(
        "--skip-download",
        action="store_true",
        help="Use --media-dir or resume raw WAVs; do not call yt-dlp",
    )
    ap.add_argument(
        "--allow-empty-transcripts",
        action="store_true",
        help="Export stub text when ASR missing (not trainable; for layout smoke tests)",
    )
    ap.add_argument(
        "--cosyvoice-repo",
        type=Path,
        default=None,
        help="CosyVoice checkout for TRAIN_HANDOFF.txt (default: COSYVOICE_REPO)",
    )
    ap.add_argument("--max-urls", type=int, default=None, help="Cap URLs processed")
    ap.add_argument(
        "--start-stage",
        default="download",
        choices=["download", "denoise", "segment", "transcribe", "export"],
    )
    ap.add_argument(
        "--stop-stage",
        default="export",
        choices=["download", "denoise", "segment", "transcribe", "export"],
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    try:
        from aoep_shared.cosyvoice_ingest.pipeline import IngestConfig, run_ingest
    except ModuleNotFoundError as exc:
        print(
            f"error: missing dependency ({exc}). "
            "Activate the repo venv:  . .venv/bin/activate\n"
            "Optional ASR/download deps:  pip install -e 'packages/shared[cosyvoice-ingest]'",
            file=sys.stderr,
        )
        return 2

    args = build_parser().parse_args(argv)
    if not args.urls_file and not args.media_dir and args.start_stage == "download":
        if not args.skip_download:
            print(
                "error: provide --urls-file and/or --media-dir "
                "(or --skip-download to resume an existing output tree)",
                file=sys.stderr,
            )
            return 2

    import os

    out = args.output_dir or Path(
        os.environ.get("COSYVOICE_INGEST_ROOT", "output/cosyvoice_ingest")
    )
    cfg = IngestConfig(
        urls_file=args.urls_file,
        media_dir=args.media_dir,
        output_dir=out,
        language=args.language,
        speaker=args.speaker,
        min_utt_sec=args.min_utt_sec,
        max_utt_sec=args.max_utt_sec,
        silence_db=args.silence_db,
        instruct=args.instruct,
        split_name=args.split_name,
        skip_download=args.skip_download,
        allow_empty_transcripts=args.allow_empty_transcripts,
        cosyvoice_repo=args.cosyvoice_repo,
        max_urls=args.max_urls,
    )
    report = run_ingest(cfg, start_stage=args.start_stage, stop_stage=args.stop_stage)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    if report.train_handoff:
        print(f"\nTrain handoff: {report.train_handoff}", file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
