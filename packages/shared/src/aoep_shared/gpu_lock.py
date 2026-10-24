"""Short GPU-lock bursts for long-running workers (the voice ingest's ASR) that must take turns with training.

The nightly and gs_run hold ~/.gs-gpu.lock (flock) for a whole job. A worker that runs for days and uses the GPU
for a few seconds at a time cannot hold that lock for its whole life, so it takes it per burst with a SHORT wait.
If the lock stays busy it proceeds without it (documented: better a slower shared GPU than a stalled ingest), and
backs off so it does not pay the wait on every segment while a long job holds the lock.
"""
from __future__ import annotations

import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Iterator

try:  # pragma: no cover - fcntl exists on Linux/macOS
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

log = logging.getLogger("aoep.gpu_lock")

_busy_until = 0.0  # monotonic time before which we skip the wait (the lock was busy for a full wait recently)


def lock_path() -> Path:
    return Path(os.environ.get("GS_GPU_LOCK") or Path.home() / ".gs-gpu.lock")


def _wait_s() -> float:
    try:
        return max(0.0, float(os.environ.get("AOEP_GPU_BURST_WAIT_S", "20")))
    except ValueError:
        return 20.0


def _backoff_s() -> float:
    try:
        return max(0.0, float(os.environ.get("AOEP_GPU_BURST_BACKOFF_S", "300")))
    except ValueError:
        return 300.0


@contextlib.contextmanager
def gpu_burst(name: str = "gpu") -> Iterator[bool]:
    """Hold the GPU lock for one short burst. Yields True when the lock is held, False when proceeding without it.

    No-op (yields True) when the caller already holds the lock (GS_GPU_LOCK_HELD=1, set by gs_run.sh and
    spark_nightly.sh) or when AOEP_GPU_BURST_LOCK=0.
    """
    global _busy_until
    if fcntl is None or os.environ.get("GS_GPU_LOCK_HELD") == "1" or os.environ.get("AOEP_GPU_BURST_LOCK", "1") == "0":
        yield True
        return
    path = lock_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as exc:
        log.warning("gpu burst %s: cannot open %s (%s); proceeding without the lock", name, path, exc)
        yield False
        return
    held = False
    try:
        deadline = time.monotonic() + (0.0 if time.monotonic() < _busy_until else _wait_s())
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.25)
        if not held:
            _busy_until = time.monotonic() + _backoff_s()
            log.warning("gpu burst %s: %s is busy; proceeding without it (will not wait again for %.0fs)", name, path, _backoff_s())
        else:
            _busy_until = 0.0
        yield held
    finally:
        if held:
            with contextlib.suppress(OSError):
                fcntl.flock(fd, fcntl.LOCK_UN)
        with contextlib.suppress(OSError):
            os.close(fd)


def _reset_for_tests() -> None:
    global _busy_until
    _busy_until = 0.0
