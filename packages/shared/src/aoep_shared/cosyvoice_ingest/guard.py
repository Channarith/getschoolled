"""Keep voice ingest and CosyVoice training from dying on memory or rate limits.

The Spark box shares one memory pool between the CPU and the GPU. A Khmer
fine-tune, a Whisper/MMS ingest, and another training job together get the
kernel OOM killer (exit -9) or a CUDA out-of-memory error. YouTube answers the
same flood with "The page needs to be reloaded." These helpers tell the queue
to wait, shrink, or back off instead of launching the next job into that wall.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

# subprocess returncode for SIGKILL is -9. A shell reports the same kill as 137.
OOM_EXIT_CODES = frozenset({-9, 137})

_MEMORY_MARKERS = (
    "out of memory",
    "cuda_error_out_of_memory",
    "cudaerrormemoryallocation",
    "nv_err_no_memory",
    "oom-kill",
    "memoryerror",
    "outofmemoryerror",
    "cuda error: out of memory",
    "exitcode: -9",
    "exitcode  : -9",
    "sigkill",
)

_RATE_MARKERS = (
    "too many requests",
    "rate limit",
    "rate-limited",
    "http error 429",
    "error 429",
    "page needs to be reloaded",
    "quota exceeded",
)

_LIMIT_CATEGORIES = frozenset({"rate_limit", "bot_check"})
_limit_streak = 0
_cooldown_until = 0.0


def reset_limit_state() -> None:
    """Clear the in-process YouTube streak. Tests call this between cases."""
    global _limit_streak, _cooldown_until
    _limit_streak = 0
    _cooldown_until = 0.0


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def is_oom_exit(code: object) -> bool:
    try:
        return int(code) in OOM_EXIT_CODES  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def is_memory_error(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _MEMORY_MARKERS)


def is_rate_limit_text(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in _RATE_MARKERS)


def available_mb(meminfo: Optional[str] = None) -> Optional[int]:
    """Megabytes of MemAvailable, or None when /proc/meminfo cannot be read."""
    if meminfo is None:
        try:
            meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
        except OSError:
            return None
    for line in meminfo.splitlines():
        if not line.startswith("MemAvailable:"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1]) // 1024
    return None


def clamp_workers(
    requested: int,
    *,
    available: Optional[int] = None,
    per_worker_mb: Optional[int] = None,
    reserve_mb: Optional[int] = None,
) -> int:
    """Fit channel workers into free RAM, leaving a reserve for the GPU job."""
    wanted = max(1, int(requested))
    each = per_worker_mb if per_worker_mb is not None else env_int("AOEP_INGEST_WORKER_MB", 6144)
    reserve = reserve_mb if reserve_mb is not None else env_int("AOEP_MEMORY_RESERVE_MB", 8192)
    if each <= 0:
        return wanted
    free = available if available is not None else available_mb()
    if free is None:
        return wanted
    room = free - max(0, reserve)
    fit = 1 if room <= 0 else max(1, room // each)
    return max(1, min(wanted, fit))


def worker_cap_violation(requested: int) -> Optional[str]:
    """Message when a hand-run queue asks for more workers than AOEP_INGEST_MAX_WORKERS (default 1) allows.

    Three hand-started workers once held about 70 GB of the Spark's shared memory and made every GPU job refuse to
    start. AOEP_INGEST_FORCE=1 overrides on purpose.
    """
    cap = max(1, env_int("AOEP_INGEST_MAX_WORKERS", 1))
    if int(requested) <= cap or os.environ.get("AOEP_INGEST_FORCE", "").strip() in {"1", "true", "yes"}:
        return None
    return (
        f"refusing --workers {int(requested)}: AOEP_INGEST_MAX_WORKERS is {cap} (each worker can hold 10-35 GB on the "
        "shared-memory Spark). Use --workers 1, raise AOEP_INGEST_MAX_WORKERS, or set AOEP_INGEST_FORCE=1 to override."
    )


def should_wait_for_memory(
    *,
    available: Optional[int],
    min_mb: int,
    active_jobs: int,
    pressure: bool = False,
) -> bool:
    """Wait only while another job is already running and memory is tight.

    The last job still starts, so a quiet machine cannot sit forever.
    ``pressure`` is set after a child was SIGKILL'd: further jobs wait until
    that retry is the only one in flight.
    """
    if active_jobs <= 0:
        return False
    if pressure:
        return True
    if min_mb <= 0 or available is None:
        return False
    return available < min_mb


def backoff_seconds(attempt: int, *, base: float, cap: float) -> float:
    if base <= 0:
        return 0.0
    step = max(1, int(attempt))
    return min(cap, base * (2 ** (step - 1)))


def limit_backoff_seconds(attempt: int, *, base: Optional[float] = None, cap: float = 900.0) -> float:
    """Exponential pause for YouTube rate limits and bot checks."""
    if base is None:
        raw = os.environ.get("YT_DLP_LIMIT_BACKOFF", "").strip()
        try:
            base = float(raw) if raw else 30.0
        except ValueError:
            base = 30.0
    return backoff_seconds(attempt, base=base, cap=cap)


def note_download_limit(category: str, *, now: Optional[float] = None) -> float:
    """Count a limit failure. Returns extra cooldown seconds once the streak trips.

    A success or any other category clears the streak. The cooldown is also
    remembered so the next URL in this process waits before it starts.
    """
    global _limit_streak, _cooldown_until
    if category not in _LIMIT_CATEGORIES:
        _limit_streak = 0
        return 0.0
    _limit_streak += 1
    need = max(1, env_int("YT_DLP_LIMIT_STREAK", 3))
    if _limit_streak < need:
        return 0.0
    _limit_streak = 0
    pause = float(max(0, env_int("YT_DLP_COOLDOWN_SEC", 120)))
    stamp = time.time() if now is None else now
    _cooldown_until = max(_cooldown_until, stamp + pause)
    return pause


def clear_download_limit() -> None:
    global _limit_streak
    _limit_streak = 0


def cooldown_remaining(now: Optional[float] = None) -> float:
    stamp = time.time() if now is None else now
    return max(0.0, _cooldown_until - stamp)


def row_hit_rate_limit(row: dict) -> bool:
    """True when a channel report is mostly YouTube limits rather than bad files."""
    counts = row.get("error_counts") or {}
    if not isinstance(counts, dict):
        counts = {}
    limited = int(counts.get("rate_limit") or 0) + int(counts.get("bot_check") or 0)
    if limited <= 0:
        error = str(row.get("error") or "")
        return "rate_limit" in error or error.startswith("bot_check")
    total = sum(int(value or 0) for value in counts.values())
    return limited * 2 >= max(1, total)


def oom_backoff_seconds(text: str) -> float:
    if not is_memory_error(text or ""):
        return 0.0
    return float(max(0, env_int("AOEP_OOM_BACKOFF_SEC", 600)))


def consume_oom_backoff(log_dir: Path) -> float:
    """Seconds to wait because the newest train log or last_failure.txt was an OOM.

    Acknowledges ``last_failure.txt`` by deleting it so a later healthy start
    does not keep sleeping. The train log stays; a newer log replaces it.
    """
    folder = Path(log_dir)
    chunks: list[str] = []
    logs = sorted(folder.glob("train-*.log"))
    if logs:
        try:
            chunks.append(logs[-1].read_text(encoding="utf-8", errors="replace")[-6000:])
        except OSError:
            pass
    failure = folder / "last_failure.txt"
    failure_text = ""
    if failure.is_file():
        try:
            failure_text = failure.read_text(encoding="utf-8", errors="replace")[-6000:]
        except OSError:
            failure_text = ""
        if failure_text:
            chunks.append(failure_text)
    delay = oom_backoff_seconds("\n".join(chunks))
    if delay and failure_text and is_memory_error(failure_text):
        try:
            failure.unlink()
        except OSError:
            pass
    return delay


def wait_for_available_memory(
    min_mb: int,
    *,
    attempts: int = 30,
    step_sec: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
    probe: Optional[Callable[[], Optional[int]]] = None,
) -> Optional[int]:
    """Poll MemAvailable until it clears ``min_mb`` or the attempts run out.

    Returns the last reading. None means the reading was unavailable, which
    does not block (a laptop without /proc/meminfo still trains).
    """
    read = probe or available_mb
    last: Optional[int] = None
    tries = max(1, int(attempts))
    for index in range(tries):
        last = read()
        if last is None or min_mb <= 0 or last >= min_mb:
            return last
        if index + 1 < tries and step_sec > 0:
            sleep(step_sec)
    return last
