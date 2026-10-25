"""Shared YouTube voice-training queue.

The RAG lab UI and the command-line ingest scripts both call this module.
One status file records progress, so a job started in the shell shows up in
the lab, and Stop in the lab stops a shell job between channels.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from .guard import (
    available_mb,
    clamp_workers,
    worker_cap_violation,
    env_int,
    is_oom_exit,
    limit_backoff_seconds,
    row_hit_rate_limit,
    should_wait_for_memory,
)

# Large news dumps. The first pass skips these unless include_news is set.
NEWS_SLUGS = frozenset(
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

STATUS_NAME = "cosyvoice_voice_queue_status.json"
STOP_NAME = "cosyvoice_voice_queue.stop"
LOG_NAME = "cosyvoice_batch_ingest.log"
REPORT_NAME = "cosyvoice_batch_ingest_report.json"

RunChannel = Callable[["ChannelJob", int | None, Path, Path], dict]


class VoiceQueueBusy(RuntimeError):
    """A queue is already running in this process or another one."""


@dataclass
class ChannelJob:
    pool_id: str
    whisper: str
    slug: str
    urls_file: str
    output_dir: str
    video_count: int

    def key(self) -> str:
        return f"{self.pool_id}/{self.slug}"

    def to_dict(self) -> dict:
        return asdict(self)


def repo_root() -> Path:
    env = os.environ.get("AOEP_REPO_ROOT", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "urls" / "cosyvoice_channels.json").is_file() and (
            parent / "packages" / "shared"
        ).is_dir():
            return parent
    return here.parents[5]


def resolve_paths(
    *,
    catalog: Optional[Path] = None,
    urls_root: Optional[Path] = None,
    output_root: Optional[Path] = None,
    cosyvoice_repo: Optional[Path] = None,
) -> dict[str, Path]:
    root = repo_root()
    catalog_path = Path(
        catalog
        or os.environ.get("AOEP_VOICE_CATALOG")
        or (root / "urls" / "cosyvoice_channels.json")
    )
    urls = Path(urls_root or os.environ.get("AOEP_VOICE_URLS_ROOT") or (root / "urls"))
    output = Path(output_root or os.environ.get("AOEP_VOICE_OUTPUT") or (root / "output"))
    repo = Path(
        cosyvoice_repo
        or os.environ.get("COSYVOICE_REPO")
        or "/home/nvidia/code/CosyVoice"
    )
    return {
        "repo_root": root,
        "catalog": catalog_path,
        "urls_root": urls,
        "output_root": output,
        "cosyvoice_repo": repo,
        "ingest_script": root / "scripts" / "cosyvoice_ingest.py",
    }


def status_path(output_root: Path) -> Path:
    return Path(output_root) / STATUS_NAME


def stop_path(output_root: Path) -> Path:
    return Path(output_root) / STOP_NAME


def pid_alive(pid: object) -> bool:
    try:
        number = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if number <= 0:
        return False
    try:
        os.kill(number, 0)
    except OSError:
        return False
    return True


def read_status(output_root: Path) -> dict:
    path = status_path(output_root)
    if not path.is_file():
        return {"running": False, "queued": 0, "done": 0, "ok": 0, "failed": 0, "log": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"running": False, "queued": 0, "done": 0, "ok": 0, "failed": 0, "log": []}
    if not isinstance(data, dict):
        return {"running": False, "queued": 0, "done": 0, "ok": 0, "failed": 0, "log": []}
    if data.get("running") and not pid_alive(data.get("pid")):
        data["running"] = False
        data["last_error"] = data.get("last_error") or "queue process exited"
    return data


def write_status(output_root: Path, payload: dict) -> None:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    path = status_path(root)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def request_stop(output_root: Path) -> None:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    stop_path(root).write_text("stop\n", encoding="utf-8")


def clear_stop(output_root: Path) -> None:
    path = stop_path(output_root)
    if path.is_file():
        path.unlink()


def stop_requested(output_root: Path, stop_event: Optional[threading.Event]) -> bool:
    if stop_event is not None and stop_event.is_set():
        return True
    return stop_path(output_root).is_file()


def _count_lines(path: Path) -> int:
    count = 0
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            text = line.strip()
            if text and not text.startswith("#"):
                count += 1
    return count


def _videos_from_status_file(urls_root: Path) -> dict[str, int]:
    path = Path(urls_root) / "cosyvoice_CORPUS_STATUS.txt"
    found: dict[str, int] = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3 or not parts[1].startswith("whisper="):
            continue
        videos = 0
        for index, part in enumerate(parts):
            if not part.startswith("videos="):
                continue
            raw = part.split("=", 1)[1]
            if not raw and index + 1 < len(parts):
                raw = parts[index + 1]
            try:
                videos = int(raw)
            except ValueError:
                videos = 0
        found[parts[0]] = videos
    return found


def load_catalog(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def catalog_summary(catalog_path: Path, urls_root: Path, output_root: Path) -> dict:
    """Pool list for the lab page. Video totals come from the status file."""
    catalog_path = Path(catalog_path)
    urls_root = Path(urls_root)
    output_root = Path(output_root)
    if not catalog_path.is_file():
        return {
            "catalog": str(catalog_path),
            "pools": [],
            "total_videos": 0,
            "note": "channel catalog not found",
        }
    catalog = load_catalog(catalog_path)
    videos = _videos_from_status_file(urls_root)
    pools = []
    total = 0
    for pool in catalog.get("pools") or []:
        pid = str(pool.get("pool_id") or "")
        if not pid:
            continue
        pool_dir = urls_root / f"cosyvoice_{pid}"
        channels = 0
        if pool_dir.is_dir():
            channels = sum(
                1
                for item in pool_dir.glob("*.txt")
                if item.is_file() and not item.stem.endswith("_all")
            )
        count = videos.get(pid)
        if count:
            total += count
        merged = output_root / f"cosyvoice_{pid}_merged"
        pools.append(
            {
                "pool_id": pid,
                "whisper": pool.get("whisper") or pid,
                "label": pool.get("label") or pid,
                "channels": channels,
                "videos": count,
                "merged": merged.is_dir(),
            }
        )
    return {
        "catalog": str(catalog_path),
        "urls_root": str(urls_root),
        "output_root": str(output_root),
        "pools": pools,
        "total_videos": total,
        "target_videos": catalog.get("target_videos"),
    }


def discover_jobs(
    catalog: dict,
    *,
    urls_root: Path,
    output_root: Path,
    pools: Optional[set[str]],
    skip_news: bool,
    min_videos: int,
) -> list[ChannelJob]:
    jobs: list[ChannelJob] = []
    urls_root = Path(urls_root)
    output_root = Path(output_root)
    for pool in catalog.get("pools") or []:
        pid = str(pool.get("pool_id") or "")
        if not pid or (pools and pid not in pools):
            continue
        whisper = str(pool.get("whisper") or pid)
        pool_dir = urls_root / f"cosyvoice_{pid}"
        if not pool_dir.is_dir():
            continue
        for urls_file in sorted(pool_dir.glob("*.txt")):
            slug = urls_file.stem
            if slug.endswith("_all"):
                continue
            if skip_news and slug.lower() in NEWS_SLUGS:
                continue
            count = _count_lines(urls_file)
            if count < min_videos:
                continue
            jobs.append(
                ChannelJob(
                    pool_id=pid,
                    whisper=whisper,
                    slug=slug,
                    urls_file=str(urls_file),
                    output_dir=str(output_root / f"cosyvoice_{pid}_{slug}"),
                    video_count=count,
                )
            )
    jobs.sort(key=lambda job: (job.video_count, job.pool_id, job.slug))
    return jobs


def cli_hint(
    *,
    pools: Sequence[str],
    workers: int,
    max_urls: Optional[int],
    max_channels: Optional[int],
    include_news: bool,
) -> str:
    parts = ["python3 scripts/cosyvoice_batch_ingest.py"]
    if pools:
        parts.append("--pool " + ",".join(pools))
    parts.append(f"--workers {workers}")
    if max_urls:
        parts.append(f"--max-urls {max_urls}")
    if max_channels:
        parts.append(f"--max-channels {max_channels}")
    if include_news:
        parts.append("--include-news")
    return " ".join(parts)


def ingest_channel(
    job: ChannelJob,
    max_urls: Optional[int],
    cosyvoice_repo: Path,
    ingest_script: Path,
) -> dict:
    """Run one channel through scripts/cosyvoice_ingest.py."""
    started = time.time()
    if not Path(ingest_script).is_file():
        return {
            "pool_id": job.pool_id,
            "slug": job.slug,
            "videos": job.video_count,
            "returncode": 2,
            "elapsed_s": 0,
            "error": f"ingest script missing: {ingest_script}",
        }
    cmd = [
        sys.executable,
        str(ingest_script),
        "--urls-file",
        job.urls_file,
        "--language",
        job.whisper,
        "--output-dir",
        job.output_dir,
        "--cosyvoice-repo",
        str(cosyvoice_repo),
        "--speaker",
        f"{job.pool_id}_{job.slug}",
        "--merge-into",
        str(Path(job.output_dir).parent / f"cosyvoice_{job.pool_id}_merged"),
        "--merge-scan-root",
        str(Path(job.output_dir).parent),
    ]
    if max_urls:
        cmd.extend(["--max-urls", str(max_urls)])
    # Kal-el voice-prep: COSYVOICE_INGEST_STAGES=download,denoise (no ASR on 8 GB).
    stages = (os.environ.get("COSYVOICE_INGEST_STAGES") or "").strip()
    if stages:
        cmd.extend(["--stages", stages])
    child_env = os.environ.copy()
    # Heavy ASR stays off when the box is already low on RAM. The parent
    # queue can still run; only this channel's transcribe step refuses.
    child_env.setdefault("AOEP_ASR_MIN_FREE_MB", "4096")
    child_env.setdefault("AOEP_ASR_SINGLE_MODEL_MB", "12288")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=child_env)
    row = {
        "pool_id": job.pool_id,
        "slug": job.slug,
        "videos": job.video_count,
        "returncode": proc.returncode,
        "elapsed_s": round(time.time() - started, 1),
        "stdout_tail": (proc.stdout or "")[-500:],
        "stderr_tail": (proc.stderr or "")[-500:],
        "error": "",
        "error_counts": {},
    }
    apply_channel_report(row, Path(job.output_dir))
    if proc.returncode and not row.get("error"):
        from .errors import classify_download_error, sanitize_process_text

        blob = sanitize_process_text((proc.stderr or "") + "\n" + (proc.stdout or ""))
        row["stderr_tail"] = blob[-500:]
        row["error"] = classify_download_error(blob) if blob else "other"
    return row


def apply_channel_report(row: dict, output_dir: Path) -> None:
    """Copy categorized errors and real tool stderr from report.json onto a queue row.

    The ingest process stderr is usually only the train-handoff path. yt-dlp and
    ffmpeg text lives on ``error_records`` inside the channel report.
    """
    from .errors import sanitize_process_text, summarize_counts

    report_path = Path(output_dir) / "report.json"
    if not report_path.is_file():
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(report, dict):
        return
    counts = report.get("error_counts") or {}
    if not isinstance(counts, dict):
        counts = {}
    records = report.get("error_records") or []
    stderr = ""
    if isinstance(records, list):
        for rec in records:
            if not isinstance(rec, dict):
                continue
            text = sanitize_process_text(str(rec.get("stderr") or ""))
            if text:
                stderr = text
                break
    row["error_counts"] = {str(key): int(value) for key, value in counts.items()}
    summary = summarize_counts(row["error_counts"])
    if summary:
        row["error"] = summary
    elif report.get("ok") is False:
        row["error"] = "export_empty" if not report.get("utterances") else "other"
    if stderr:
        row["stderr_tail"] = stderr[-500:]
    row["partial"] = bool(report.get("partial"))
    row["utterances"] = int(report.get("utterances") or 0)


def _result_line(row: dict) -> str:
    return (
        f"[{row.get('pool_id')}/{row.get('slug')}] "
        f"rc={row.get('returncode')} elapsed={row.get('elapsed_s')}s "
        f"videos={row.get('videos')}"
    )


def execute_queue(
    *,
    catalog_path: Path,
    urls_root: Path,
    output_root: Path,
    cosyvoice_repo: Path,
    ingest_script: Path,
    pools: Optional[set[str]],
    workers: int,
    max_urls: Optional[int],
    max_channels: Optional[int],
    include_news: bool,
    min_videos: int,
    stop_event: Optional[threading.Event] = None,
    run_channel: Optional[RunChannel] = None,
    sleeper: Optional[Callable[[float], None]] = None,
) -> int:
    """Discover channel lists and ingest them. Returns 0, 1, or 2 (nothing queued)."""
    output_root = Path(output_root)
    pool_list = sorted(pools) if pools else []
    pause = sleeper or time.sleep
    requested_workers = max(1, int(workers))
    worker_count = clamp_workers(requested_workers)
    state: dict = {
        "running": True,
        "stopped": False,
        "phase": "discover",
        "pid": os.getpid(),
        "started_at": time.time(),
        "finished_at": None,
        "pools": pool_list,
        "workers": worker_count,
        "workers_requested": requested_workers,
        "include_news": bool(include_news),
        "max_urls": max_urls,
        "max_channels": max_channels,
        "queued": 0,
        "done": 0,
        "ok": 0,
        "failed": 0,
        "current": [],
        "last_error": "",
        "log": [],
        "recent": [],
        "cli": cli_hint(
            pools=pool_list,
            workers=worker_count,
            max_urls=max_urls,
            max_channels=max_channels,
            include_news=include_news,
        ),
    }
    write_status(output_root, state)
    if not Path(catalog_path).is_file():
        state["running"] = False
        state["phase"] = "idle"
        state["last_error"] = f"catalog not found: {catalog_path}"
        state["finished_at"] = time.time()
        write_status(output_root, state)
        print(state["last_error"], file=sys.stderr)
        return 2

    catalog = load_catalog(Path(catalog_path))
    jobs = discover_jobs(
        catalog,
        urls_root=Path(urls_root),
        output_root=output_root,
        pools=pools,
        skip_news=not include_news,
        min_videos=min_videos,
    )
    if max_channels:
        jobs = jobs[: max(0, int(max_channels))]
    state["queued"] = len(jobs)
    state["phase"] = "ingest" if jobs else "idle"
    if not jobs:
        state["running"] = False
        state["finished_at"] = time.time()
        state["last_error"] = (
            "No channel URL lists found. Run: "
            "python3 scripts/cosyvoice_expand_channels.py --workers 8"
        )
        write_status(output_root, state)
        print(state["last_error"], file=sys.stderr)
        return 2
    write_status(output_root, state)
    print(
        f"batch ingest: {len(jobs)} channels, workers={state['workers']}, "
        f"skip_news={not include_news}",
        flush=True,
    )

    runner = run_channel or ingest_channel
    pending: queue.Queue[ChannelJob] = queue.Queue()
    for job in jobs:
        pending.put(job)
    lock = threading.Lock()
    log_path = output_root / LOG_NAME
    results: list[dict] = []

    def record(row: dict, current_key: str) -> None:
        line = _result_line(row)
        with lock:
            state["done"] = int(state["done"]) + 1
            if row.get("returncode") == 0:
                state["ok"] = int(state["ok"]) + 1
            else:
                state["failed"] = int(state["failed"]) + 1
                state["last_error"] = row.get("error") or line
            current = [item for item in state["current"] if item != current_key]
            state["current"] = current
            log = list(state["log"])
            log.append(line)
            state["log"] = log[-80:]
            recent = list(state["recent"])
            recent.append(
                {
                    "pool_id": row.get("pool_id"),
                    "slug": row.get("slug"),
                    "videos": row.get("videos"),
                    "returncode": row.get("returncode"),
                    "elapsed_s": row.get("elapsed_s"),
                    "error": row.get("error") or "",
                }
            )
            state["recent"] = recent[-40:]
            results.append(row)
            write_status(output_root, state)
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    pressure = {"on": False}
    oom_tries: dict[str, int] = {}
    limit_hits = {"n": 0}
    pause_until = {"t": 0.0}
    min_free = env_int("AOEP_INGEST_MIN_FREE_MB", 8192)

    def _hold_for_room() -> None:
        """Sleep while a rate-limit cooldown or a memory crush is in effect."""
        waits = max(1, env_int("AOEP_MEMORY_WAIT_ATTEMPTS", 30))
        step = float(env_int("AOEP_MEMORY_WAIT_SEC", 5))
        for _ in range(waits):
            if stop_requested(output_root, stop_event):
                return
            with lock:
                cool = pause_until["t"] - time.time()
                active = len(state["current"])
                pressed = bool(pressure["on"])
            if cool > 0:
                pause(min(cool, step if step > 0 else cool))
                continue
            free = available_mb()
            if not should_wait_for_memory(
                available=free,
                min_mb=min_free,
                active_jobs=active,
                pressure=pressed,
            ):
                return
            if step <= 0:
                return
            pause(step)

    def worker() -> None:
        while not stop_requested(output_root, stop_event):
            _hold_for_room()
            if stop_requested(output_root, stop_event):
                return
            try:
                job = pending.get_nowait()
            except queue.Empty:
                return
            with lock:
                if pressure["on"] and state["current"]:
                    busy = True
                else:
                    busy = False
                    state["current"] = list(state["current"]) + [job.key()]
                    write_status(output_root, state)
            if busy:
                pending.put(job)
                pause(float(env_int("AOEP_MEMORY_WAIT_SEC", 5)) or 0.05)
                continue
            try:
                row = runner(job, max_urls, Path(cosyvoice_repo), Path(ingest_script))
            except Exception as exc:  # noqa: BLE001
                row = {
                    "pool_id": job.pool_id,
                    "slug": job.slug,
                    "videos": job.video_count,
                    "returncode": -1,
                    "elapsed_s": 0,
                    "error": str(exc),
                }
            if is_oom_exit(row.get("returncode")) and oom_tries.get(job.key(), 0) < 1:
                with lock:
                    oom_tries[job.key()] = oom_tries.get(job.key(), 0) + 1
                    pressure["on"] = True
                row["error"] = row.get("error") or "oom"
                with lock:
                    state["last_error"] = "oom"
                    state["current"] = [
                        item for item in state["current"] if item != job.key()
                    ] + ["oom-backoff"]
                    log = list(state["log"])
                    log.append(_result_line(row) + " oom-retry")
                    state["log"] = log[-80:]
                    write_status(output_root, state)
                print(_result_line(row) + " oom-retry", flush=True)
                delay = float(env_int("AOEP_OOM_BACKOFF_SEC", 600))
                remaining = delay
                while remaining > 0 and not stop_requested(output_root, stop_event):
                    chunk = min(remaining, 5.0)
                    pause(chunk)
                    remaining -= chunk
                with lock:
                    state["current"] = [
                        item for item in state["current"] if item != "oom-backoff"
                    ]
                    write_status(output_root, state)
                if not stop_requested(output_root, stop_event):
                    pending.put(job)
                continue
            if is_oom_exit(row.get("returncode")):
                row["error"] = row.get("error") or "oom"
                with lock:
                    pressure["on"] = True
            record(row, job.key())
            if row_hit_rate_limit(row):
                with lock:
                    limit_hits["n"] += 1
                    delay = limit_backoff_seconds(limit_hits["n"])
                    if delay > 0:
                        pause_until["t"] = max(pause_until["t"], time.time() + delay)
                        state["last_error"] = row.get("error") or "rate_limit"
                        write_status(output_root, state)

    threads = [
        threading.Thread(target=worker, name=f"voice-queue-{index}", daemon=True)
        for index in range(state["workers"])
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    stopped = stop_requested(output_root, stop_event)
    state["running"] = False
    state["stopped"] = stopped
    state["phase"] = "stopped" if stopped else "done"
    state["finished_at"] = time.time()
    state["current"] = []
    write_status(output_root, state)
    report = output_root / REPORT_NAME
    report.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    ok = sum(1 for row in results if row.get("returncode") == 0)
    print(f"done: {ok}/{len(results)} channels ok; report={report}", flush=True)
    if stopped:
        return 0 if ok and state["failed"] == 0 else 1
    return 0 if ok == len(results) and results else 1


def assert_queue_free(output_root: Path) -> None:
    status = read_status(output_root)
    if status.get("running") and pid_alive(status.get("pid")):
        raise VoiceQueueBusy(
            f"voice queue is already running (pid {status.get('pid')})"
        )


def cli_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Queue YouTube channels into CosyVoice training data. "
        "Same queue the RAG lab Voice training tab runs."
    )
    parser.add_argument("--catalog", type=Path, default=None)
    parser.add_argument("--urls-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--pool", default="", help="Comma-separated pool ids")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--include-news", action="store_true")
    parser.add_argument("--min-videos", type=int, default=1)
    parser.add_argument("--max-urls", type=int, default=None)
    parser.add_argument("--max-channels", type=int, default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true", help="Ask the running queue to stop")
    parser.add_argument(
        "--cosyvoice-repo",
        type=Path,
        default=None,
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = resolve_paths(
        catalog=args.catalog,
        urls_root=args.urls_root,
        output_root=args.output_root,
        cosyvoice_repo=args.cosyvoice_repo,
    )
    cap_message = worker_cap_violation(args.workers)
    if cap_message and not (args.status or args.stop):
        print(f"cosyvoice_batch_ingest: {cap_message}", file=sys.stderr)
        return 2
    if args.status:
        status_file = paths["urls_root"] / "cosyvoice_CORPUS_STATUS.txt"
        if status_file.is_file():
            print(status_file.read_text(encoding="utf-8"))
        else:
            summary = catalog_summary(
                paths["catalog"], paths["urls_root"], paths["output_root"]
            )
            print(json.dumps(summary, indent=2))
        live = read_status(paths["output_root"])
        if live.get("running") or live.get("done"):
            print(json.dumps({"queue": live}, indent=2))
        return 0
    if args.stop:
        request_stop(paths["output_root"])
        print(f"stop requested: {stop_path(paths['output_root'])}")
        return 0
    try:
        assert_queue_free(paths["output_root"])
    except VoiceQueueBusy as exc:
        print(str(exc), file=sys.stderr)
        return 1
    clear_stop(paths["output_root"])
    pools = {part.strip() for part in args.pool.split(",") if part.strip()} or None
    try:
        return execute_queue(
            catalog_path=paths["catalog"],
            urls_root=paths["urls_root"],
            output_root=paths["output_root"],
            cosyvoice_repo=paths["cosyvoice_repo"],
            ingest_script=paths["ingest_script"],
            pools=pools,
            workers=max(1, args.workers),
            max_urls=args.max_urls,
            max_channels=args.max_channels,
            include_news=bool(args.include_news),
            min_videos=max(1, args.min_videos),
        )
    except KeyboardInterrupt:
        request_stop(paths["output_root"])
        print("stop requested", file=sys.stderr)
        return 1


# Imported by the lab so a test can patch this name.
__all__ = [
    "ChannelJob",
    "NEWS_SLUGS",
    "VoiceQueueBusy",
    "assert_queue_free",
    "catalog_summary",
    "clear_stop",
    "cli_hint",
    "cli_main",
    "discover_jobs",
    "execute_queue",
    "ingest_channel",
    "read_status",
    "repo_root",
    "request_stop",
    "resolve_paths",
    "write_status",
]
