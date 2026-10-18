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

  # Kal-el (no GPU service): download + denoise only. Default dir is
  # output/kalel/ingest when --output-dir is omitted.
  python3 scripts/cosyvoice_ingest.py \\
    --urls-file urls.txt --language km --stages download,denoise \\
    --output-dir output/kalel/km_example

  # Spark, after: rsync -a --ignore-existing output/kalel/ HOST:output/inbox/kalel/
  python3 scripts/cosyvoice_ingest.py \\
    --inbox output/inbox/kalel --stages segment,transcribe,export \\
    --output-dir output/spark/from-kalel --language km

  # Rebuild language merge pool only (no download/ASR):
  python3 scripts/cosyvoice_ingest.py --merge-only --language km

  python3 scripts/cosyvoice_ingest.py --help

Env: COSYVOICE_REPO, COSYVOICE_INGEST_ROOT, COSYVOICE_MERGE_INTO,
COSYVOICE_MERGE_SCAN_ROOT, AOEP_ASR_MODEL / WHISPER_MODEL, YT_DLP_BIN,
AOEP_ASR_DEVICE, AOEP_ASR_COMPUTE_TYPE.

YouTube bot checks / HTTP 403: set YT_DLP_COOKIES or COSYVOICE_COOKIES_FILE
to a Netscape cookies file you already have. This tool does not create or
read that file into logs. Pace downloads with YT_DLP_MIN_INTERVAL (seconds,
default 1) and YT_DLP_BACKOFF (default 2). The cosyvoice-ingest extra pins
yt-dlp==2026.8.19.

Every successful export also rebuilds ``output/cosyvoice_<lang>_merged``
(unless ``--no-merge``). Train against that merged handoff.

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
    ap.add_argument(
        "--stages",
        default=None,
        help=(
            "Comma-separated stages to run, e.g. download,denoise. "
            "Overrides --start-stage and --stop-stage. "
            "download,denoise with no --output-dir writes output/kalel/ingest."
        ),
    )
    ap.add_argument(
        "--inbox",
        type=Path,
        default=None,
        help=(
            "Kal-el handoff root (output/inbox/kalel or one channel dir). "
            "Raw and clean wavs are hardlinked in with ignore-existing, "
            "then the selected stages run."
        ),
    )
    ap.add_argument(
        "--merge-into",
        type=Path,
        default=None,
        help="Combined recipe root (default: output/cosyvoice_<lang>_merged)",
    )
    ap.add_argument(
        "--merge-scan-root",
        type=Path,
        default=None,
        help="Parent dir scanned for channel recipes (default: parent of --output-dir)",
    )
    ap.add_argument(
        "--no-merge",
        action="store_true",
        help="Skip rebuilding the language-wide merged train recipe",
    )
    ap.add_argument(
        "--merge-only",
        action="store_true",
        help="Only rebuild the merged recipe from existing channel exports",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    try:
        from aoep_shared.cosyvoice_ingest.merge import (
            default_merge_into,
            merge_language_pool,
        )
        from aoep_shared.cosyvoice_ingest.pipeline import (
            IngestConfig,
            discover_inbox_channels,
            parse_stages,
            run_ingest,
        )
    except ModuleNotFoundError as exc:
        print(
            f"error: missing dependency ({exc}). "
            "Activate the repo venv:  . .venv/bin/activate\n"
            "Optional ASR/download deps:  pip install -e 'packages/shared[cosyvoice-ingest]'",
            file=sys.stderr,
        )
        return 2

    args = build_parser().parse_args(argv)
    import os

    if args.merge_only:
        merge_into = args.merge_into or Path(
            os.environ.get("COSYVOICE_MERGE_INTO", "") or default_merge_into(args.language)
        )
        scan_root = args.merge_scan_root or Path(
            os.environ.get("COSYVOICE_MERGE_SCAN_ROOT", "output")
        )
        repo = args.cosyvoice_repo or Path(
            os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")
        )
        merge_report = merge_language_pool(
            language=args.language,
            merge_into=merge_into,
            scan_roots=[scan_root],
            split_name=args.split_name,
            cosyvoice_repo=repo if repo.exists() else repo,
        )
        print(json.dumps(merge_report.to_dict(), indent=2, ensure_ascii=False))
        if merge_report.train_handoff:
            print(f"\nTrain handoff: {merge_report.train_handoff}", file=sys.stderr)
        return 0 if merge_report.ok else 1

    try:
        stage_list = parse_stages(args.stages) if args.stages else None
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    runs_download = (
        "download" in stage_list if stage_list is not None else args.start_stage == "download"
    )
    if (
        runs_download
        and not args.urls_file
        and not args.media_dir
        and not args.skip_download
        and not args.inbox
    ):
        print(
            "error: provide --urls-file and/or --media-dir "
            "(or --skip-download to resume an existing output tree, "
            "or --inbox, or --merge-only)",
            file=sys.stderr,
        )
        return 2

    early_only = stage_list is not None and set(stage_list) <= {"download", "denoise"}
    if args.output_dir is not None:
        out_root = args.output_dir
    elif early_only:
        out_root = Path(os.environ.get("COSYVOICE_KALEL_ROOT", "output/kalel/ingest"))
    else:
        out_root = Path(os.environ.get("COSYVOICE_INGEST_ROOT", "output/cosyvoice_ingest"))

    jobs: list[tuple[Path, Path | None]] = [(out_root, None)]
    if args.inbox:
        channels = discover_inbox_channels(args.inbox)
        if not channels:
            print(f"error: no 01_raw/ or 02_clean/ under {args.inbox}", file=sys.stderr)
            return 2
        if len(channels) == 1 and args.output_dir is not None:
            jobs = [(out_root, channels[0])]
        elif len(channels) == 1 and args.output_dir is None:
            jobs = [(channels[0], channels[0])]
        else:
            parent = args.output_dir or Path("output/spark/from-kalel")
            jobs = [(parent / channel.name, channel) for channel in channels]

    exit_code = 0
    reports = []
    for dest, inbox in jobs:
        cfg = IngestConfig(
            urls_file=args.urls_file,
            media_dir=args.media_dir,
            output_dir=dest,
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
            merge=not args.no_merge,
            merge_into=args.merge_into,
            merge_scan_root=args.merge_scan_root,
            inbox_dir=inbox,
        )
        report = run_ingest(
            cfg,
            start_stage=args.start_stage,
            stop_stage=args.stop_stage,
            stages=stage_list,
        )
        reports.append(report.to_dict())
        if not report.ok:
            exit_code = 1
    payload = reports[0] if len(reports) == 1 else {"channels": reports}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if report.error_counts:
        summary = ",".join(
            f"{name}:{count}" for name, count in sorted(report.error_counts.items())
        )
        print(f"ingest errors: {summary}", file=sys.stderr)
    if report.merge_train_handoff:
        print(f"\nMerged train handoff: {report.merge_train_handoff}", file=sys.stderr)
    elif report.train_handoff:
        print(f"\nTrain handoff: {report.train_handoff}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
