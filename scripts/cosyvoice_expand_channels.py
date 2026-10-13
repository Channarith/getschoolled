#!/usr/bin/env python3
"""Expand urls/cosyvoice_channels.json → per-pool video URL lists via yt-dlp.

Writes:
  urls/cosyvoice_<pool_id>/<slug>.txt
  urls/cosyvoice_<pool_id>_all.txt
  urls/cosyvoice_CORPUS_STATUS.txt

Example:
  python3 scripts/cosyvoice_expand_channels.py --workers 8
  python3 scripts/cosyvoice_expand_channels.py --pool zh,yue,en_gb --workers 4
  python3 scripts/cosyvoice_expand_channels.py --skip-nonempty --workers 8
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]


def _slug(handle_or_url: str) -> str:
    text = (handle_or_url or "").strip()
    if "list=" in text:
        m = re.search(r"list=([A-Za-z0-9_-]+)", text)
        return f"playlist_{m.group(1)[:40]}" if m else "playlist"
    text = text.rstrip("/").split("/")[-1]
    text = text.lstrip("@")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return (text or "channel")[:64].lower()


def _yt_dlp() -> str:
    return os.environ.get("YT_DLP_BIN", "yt-dlp")


def expand_source(source: str, dest: Path) -> Tuple[str, int, str]:
    """Expand one channel handle (@x) or playlist URL into dest. Returns (slug, n, err)."""
    slug = _slug(source)
    dest.parent.mkdir(parents=True, exist_ok=True)
    urls: List[str] = []
    err = ""
    bin_ = _yt_dlp()
    if source.startswith("http"):
        targets = [source]
        playlist_flag = ["--yes-playlist"]
    else:
        handle = source if source.startswith("@") else f"@{source}"
        targets = [
            f"https://www.youtube.com/{handle}/videos",
            f"https://www.youtube.com/{handle}/shorts",
        ]
        playlist_flag = []

    for target in targets:
        cmd = [
            bin_,
            "--flat-playlist",
            "--ignore-errors",
            *playlist_flag,
            "--print",
            "https://www.youtube.com/watch?v=%(id)s",
            "--no-warnings",
            target,
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=1800,
            )
        except subprocess.TimeoutExpired:
            err = f"timeout:{target}"
            continue
        except FileNotFoundError:
            return slug, 0, "yt-dlp not found"
        stderr = (proc.stderr or "")[-300:]
        # Missing shorts tab is normal — not a hard failure if /videos worked.
        soft = "does not have a shorts tab" in stderr.lower() or (
            "/shorts" in target and "404" in stderr
        )
        if proc.returncode != 0 and not proc.stdout.strip():
            if soft:
                continue
            err = stderr or (proc.stdout or "yt-dlp failed")[-200:]
            continue
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("http"):
                urls.append(line)

    # Fallback: bare channel URL when tab endpoints failed
    if not urls and not source.startswith("http"):
        handle = source if source.startswith("@") else f"@{source}"
        cmd = [
            bin_,
            "--flat-playlist",
            "--ignore-errors",
            "--print",
            "https://www.youtube.com/watch?v=%(id)s",
            "--no-warnings",
            f"https://www.youtube.com/{handle}",
        ]
        try:
            proc = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=1800
            )
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("http"):
                    urls.append(line)
            if not urls and proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "yt-dlp failed")[-200:]
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:200]

    # dedupe preserve order
    seen = set()
    ordered = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    dest.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    return slug, len(ordered), err


def write_pool_all(pool_dir: Path, all_path: Path) -> int:
    seen = set()
    ordered: List[str] = []
    for f in sorted(pool_dir.glob("*.txt")):
        for line in f.read_text(encoding="utf-8").splitlines():
            u = line.strip()
            if u and u not in seen:
                seen.add(u)
                ordered.append(u)
    all_path.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    return len(ordered)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "urls" / "cosyvoice_channels.json",
    )
    ap.add_argument("--pool", default="", help="Comma pool_ids (default: all)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument(
        "--skip-nonempty",
        action="store_true",
        help="Skip sources whose URL file already lists at least one video",
    )
    ap.add_argument(
        "--urls-root",
        type=Path,
        default=ROOT / "urls",
        help="Parent for cosyvoice_<pool>/ directories",
    )
    args = ap.parse_args(argv)

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    want = {p.strip() for p in args.pool.split(",") if p.strip()} or None
    pools = catalog.get("pools") or []
    jobs: List[Tuple[str, str, str, Path]] = []  # pool_id, whisper, source, dest
    for pool in pools:
        pid = pool["pool_id"]
        if want and pid not in want:
            continue
        pool_dir = args.urls_root / f"cosyvoice_{pid}"
        pool_dir.mkdir(parents=True, exist_ok=True)
        for ch in pool.get("channels") or []:
            dest = pool_dir / f"{_slug(ch)}.txt"
            jobs.append((pid, pool.get("whisper", pid), ch, dest))
        for pl in pool.get("playlists") or []:
            dest = pool_dir / f"{_slug(pl)}.txt"
            jobs.append((pid, pool.get("whisper", pid), pl, dest))

    if args.skip_nonempty:
        kept = []
        skipped = 0
        for job in jobs:
            dest = job[3]
            if dest.is_file() and any(line.strip() for line in dest.read_text(encoding="utf-8").splitlines()):
                skipped += 1
                continue
            kept.append(job)
        jobs = kept
        print(f"skip-nonempty: left {skipped} existing lists, expanding {len(jobs)}", flush=True)

    print(f"expanding {len(jobs)} sources with {args.workers} workers…", flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {
            ex.submit(expand_source, source, dest): (pid, whisper, source, dest)
            for pid, whisper, source, dest in jobs
        }
        for fut in concurrent.futures.as_completed(futs):
            pid, whisper, source, dest = futs[fut]
            slug, n, err = fut.result()
            status = "ok" if n else f"empty:{err[:80]}"
            print(f"[{pid}] {slug}: {n}  ({status})", flush=True)
            results.append(
                {
                    "pool_id": pid,
                    "whisper": whisper,
                    "source": source,
                    "slug": slug,
                    "path": str(dest.relative_to(ROOT)) if dest.is_relative_to(ROOT) else str(dest),
                    "videos": n,
                    "error": err,
                }
            )

    # per-pool all + status
    status_lines = [
        "CosyVoice multi-language corpus status",
        "=====================================",
        f"catalog: {args.catalog}",
        f"target_videos: {catalog.get('target_videos')}",
        "",
    ]
    grand = 0
    for pool in pools:
        pid = pool["pool_id"]
        if want and pid not in want:
            continue
        pool_dir = args.urls_root / f"cosyvoice_{pid}"
        all_path = args.urls_root / f"cosyvoice_{pid}_all.txt"
        n = write_pool_all(pool_dir, all_path) if pool_dir.is_dir() else 0
        grand += n
        status_lines.append(
            f"  {pid:10s}  whisper={pool.get('whisper'):4s}  "
            f"videos={n:7d}  label={pool.get('label')}"
        )
    status_lines += ["", f"TOTAL unique (sum of pool all-files): {grand}", ""]
    status_path = args.urls_root / "cosyvoice_CORPUS_STATUS.txt"
    status_path.write_text("\n".join(status_lines) + "\n", encoding="utf-8")
    (args.urls_root / "cosyvoice_expand_report.json").write_text(
        json.dumps(
            {"total_listed": grand, "results": results, "status": str(status_path)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("\n".join(status_lines), flush=True)
    print(f"wrote {status_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
