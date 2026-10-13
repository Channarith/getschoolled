#!/usr/bin/env python3
"""Async / multi-worker CosyVoice ingest across language pools (Spark-friendly).

Reads ``urls/cosyvoice_channels.json`` + expanded ``urls/cosyvoice_<pool>/*.txt``,
runs up to ``--workers`` channel ingests in parallel, merges each pool after
every channel finishes.

Examples:
  # expand then ingest (non-news first)
  python3 scripts/cosyvoice_expand_channels.py --workers 8
  python3 scripts/cosyvoice_batch_ingest.py --workers 3 --skip-news

  # one pool
  python3 scripts/cosyvoice_batch_ingest.py --pool zh,yue,en_gb --workers 2

  # status only
  python3 scripts/cosyvoice_batch_ingest.py --status
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

# Large news dumps — include with --include-news
_DEFAULT_NEWS_SLUGS = frozenset(
    {
        "rfi_km",
        "rfa_khmer",
        "khmerptv",
        "vttoday",
        "cctv",
        "cgtnofficial",
        "xinhuanewsagency",
        "peopledailychina",
        "bbcnews",
        "bbc",
        "skynews",
        "itvnews",
        "guardiannews",
        "abcnewsaustralia",
        "7newsaustralia",
        "9newsaustralia",
        "abs-cbnnews",
        "anc",
        "vtv24",
        "vtcnow",
        "thaipbs",
        "nationtv22",
        "rtve",
        "france24",
        "franceinfo",
        "dwnews",
        "tagesschau",
        "rtnews",
        "aljazeeraarabic",
        "ddnews",
        "ndtv",
        "aajtak",
        "nos",
        "tvn24",
        "trthaber",
        "rai",
        "skytg24",
        "kompastv",
        "metrotv",
        "ytnnews",
        "jtbcnews",
        "nhkworldnews",
        "tvbsnews",
        "setinews",
        "ftvnews",
        "rthk",
        "tvbnews",
        "nownews",
    }
)


@dataclass
class ChannelJob:
    pool_id: str
    whisper: str
    slug: str
    urls_file: Path
    output_dir: Path
    video_count: int


def _load_catalog(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_jobs(
    catalog: dict,
    *,
    urls_root: Path,
    pools: Optional[set[str]],
    skip_news: bool,
    min_videos: int,
) -> List[ChannelJob]:
    jobs: List[ChannelJob] = []
    for pool in catalog.get("pools") or []:
        pid = pool["pool_id"]
        if pools and pid not in pools:
            continue
        whisper = pool.get("whisper") or pid
        pool_dir = urls_root / f"cosyvoice_{pid}"
        if not pool_dir.is_dir():
            continue
        for urls_file in sorted(pool_dir.glob("*.txt")):
            slug = urls_file.stem
            if skip_news and slug.lower() in _DEFAULT_NEWS_SLUGS:
                continue
            n = sum(1 for line in urls_file.read_text(encoding="utf-8").splitlines() if line.strip())
            if n < min_videos:
                continue
            jobs.append(
                ChannelJob(
                    pool_id=pid,
                    whisper=whisper,
                    slug=slug,
                    urls_file=urls_file,
                    output_dir=ROOT / "output" / f"cosyvoice_{pid}_{slug}",
                    video_count=n,
                )
            )
    return jobs


def run_ingest(job: ChannelJob, *, repo: Path, max_urls: Optional[int]) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "cosyvoice_ingest.py"),
        "--urls-file",
        str(job.urls_file),
        "--language",
        job.whisper,
        "--output-dir",
        str(job.output_dir),
        "--cosyvoice-repo",
        str(repo),
        "--speaker",
        f"{job.pool_id}_{job.slug}",
        "--merge-into",
        str(ROOT / "output" / f"cosyvoice_{job.pool_id}_merged"),
        "--merge-scan-root",
        str(ROOT / "output"),
    ]
    if max_urls:
        cmd.extend(["--max-urls", str(max_urls)])
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    elapsed = time.time() - started
    return {
        "pool_id": job.pool_id,
        "slug": job.slug,
        "videos": job.video_count,
        "returncode": proc.returncode,
        "elapsed_s": round(elapsed, 1),
        "stdout_tail": (proc.stdout or "")[-500:],
        "stderr_tail": (proc.stderr or "")[-500:],
    }


def corpus_status(urls_root: Path) -> str:
    status = urls_root / "cosyvoice_CORPUS_STATUS.txt"
    if status.is_file():
        return status.read_text(encoding="utf-8")
    # fallback scan
    lines = ["CosyVoice corpus (live scan)", ""]
    total = 0
    for all_f in sorted(urls_root.glob("cosyvoice_*_all.txt")):
        n = sum(1 for line in all_f.read_text(encoding="utf-8").splitlines() if line.strip())
        total += n
        lines.append(f"  {all_f.name}: {n}")
    lines.append(f"TOTAL={total}")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, default=ROOT / "urls" / "cosyvoice_channels.json")
    ap.add_argument("--urls-root", type=Path, default=ROOT / "urls")
    ap.add_argument("--pool", default="", help="Comma pool_ids")
    ap.add_argument("--workers", type=int, default=3, help="Parallel channel ingests")
    ap.add_argument(
        "--include-news",
        action="store_true",
        help="Include large news channels (default: skip for first pass)",
    )
    ap.add_argument("--min-videos", type=int, default=1)
    ap.add_argument("--max-urls", type=int, default=None, help="Cap per channel (smoke)")
    ap.add_argument("--max-channels", type=int, default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument(
        "--cosyvoice-repo",
        type=Path,
        default=Path(os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")),
    )
    args = ap.parse_args(argv)

    if args.status:
        print(corpus_status(args.urls_root))
        return 0

    skip_news = not bool(args.include_news)
    catalog = _load_catalog(args.catalog)
    pools = {p.strip() for p in args.pool.split(",") if p.strip()} or None
    jobs = discover_jobs(
        catalog,
        urls_root=args.urls_root,
        pools=pools,
        skip_news=skip_news,
        min_videos=args.min_videos,
    )
    # Prefer smaller lesson channels first so merge gets data sooner
    jobs.sort(key=lambda j: (j.video_count, j.pool_id, j.slug))
    if args.max_channels:
        jobs = jobs[: max(0, args.max_channels)]

    print(
        f"batch ingest: {len(jobs)} channels, workers={args.workers}, "
        f"skip_news={skip_news}",
        flush=True,
    )
    if not jobs:
        print(
            "No channel URL lists found. Run:\n"
            "  python3 scripts/cosyvoice_expand_channels.py --workers 8",
            file=sys.stderr,
        )
        return 2

    log_path = ROOT / "output" / "cosyvoice_batch_ingest.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {
            ex.submit(run_ingest, job, repo=args.cosyvoice_repo, max_urls=args.max_urls): job
            for job in jobs
        }
        for fut in concurrent.futures.as_completed(futs):
            job = futs[fut]
            try:
                row = fut.result()
            except Exception as exc:  # noqa: BLE001
                row = {
                    "pool_id": job.pool_id,
                    "slug": job.slug,
                    "videos": job.video_count,
                    "returncode": -1,
                    "error": str(exc),
                }
            results.append(row)
            line = (
                f"[{row.get('pool_id')}/{row.get('slug')}] "
                f"rc={row.get('returncode')} elapsed={row.get('elapsed_s')}s "
                f"videos={row.get('videos')}"
            )
            print(line, flush=True)
            with log_path.open("a", encoding="utf-8") as log:
                log.write(line + "\n")

    report = ROOT / "output" / "cosyvoice_batch_ingest_report.json"
    report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for r in results if r.get("returncode") == 0)
    print(f"done: {ok}/{len(results)} channels ok; report={report}", flush=True)
    print(corpus_status(args.urls_root))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
