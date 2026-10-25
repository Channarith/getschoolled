"""Progress of a clone run, readable while it runs: OUT/progress.json (summary) and OUT/progress/worker-<k>.json (one per worker).

`bakeoff status --out OUT` turns them, plus the manifests on disk, into a table with a bar, the current unit, an ETA and DONE/RUNNING.
Counting finished files alone cannot show progress on a re-run (they all exist already); the worker files can.
"""
from __future__ import annotations

import json
import os
import time
from collections import deque
from pathlib import Path

PROGRESS_DIR = "progress"
SUMMARY = "progress.json"
MIN_WAV_BYTES = 2000


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError):
        return True
    return True


class WorkerProgress:
    """One worker's view: what it is doing now, how long recent clips took, how many it has finished."""

    def __init__(self, out: Path, worker: int, clips_total: int):
        self.out, self.worker = Path(out), worker
        self.path = self.out / PROGRESS_DIR / f"worker-{worker}.json"
        self.state = {"worker": worker, "pid": os.getpid(), "started": time.time(), "updated": time.time(), "current": None,
                      "clips_total": clips_total, "done": 0, "failed": 0, "skipped_existing": 0, "recent_clip_seconds": [], "finished": False}
        self._recent: deque = deque(maxlen=20)
        self.flush()

    def flush(self) -> None:
        self.state["updated"] = time.time()
        self.state["recent_clip_seconds"] = [round(x, 2) for x in self._recent]
        atomic_write(self.path, self.state)

    def begin(self, speaker: str, model: str, lang: str) -> None:
        self.state["current"] = {"speaker": speaker, "model": model, "lang": lang}
        self.flush()

    def clip(self, status: str, seconds: float | None = None) -> None:
        if status == "ok":
            self.state["done"] += 1
            if seconds:
                self._recent.append(seconds)
        elif status == "failed":
            self.state["failed"] += 1
        elif status == "skipped_existing":
            self.state["skipped_existing"] += 1
        self.flush()

    def finish(self) -> None:
        self.state["finished"] = True
        self.state["current"] = None
        self.flush()


def read_workers(out: Path) -> list[dict]:
    rows = []
    d = Path(out) / PROGRESS_DIR
    for p in sorted(d.glob("worker-*.json")) if d.is_dir() else []:
        try:
            rows.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return rows


def aggregate(out: Path) -> dict:
    """Merge the plan and the worker files into OUT/progress.json and return it."""
    out = Path(out)
    summary_path = out / SUMMARY
    try:
        base = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        base = {}
    workers = read_workers(out)
    running = [w for w in workers if not w.get("finished") and pid_alive(w.get("pid"))]
    base.update({
        "updated": time.time(),
        "workers": [{k: w.get(k) for k in ("worker", "pid", "current", "done", "failed", "skipped_existing", "finished")} for w in workers],
        "clips_done": sum(w.get("done", 0) for w in workers),
        "clips_failed": sum(w.get("failed", 0) for w in workers),
        "clips_skipped_existing": sum(w.get("skipped_existing", 0) for w in workers),
        "running": bool(running),
    })
    atomic_write(summary_path, base)
    return base


def write_plan(out: Path, units: list[dict], workers: int) -> None:
    """units: [{speaker, model, lang, total}] for the whole run (every worker's share)."""
    out = Path(out)
    for stale in (out / PROGRESS_DIR).glob("worker-*.json") if (out / PROGRESS_DIR).is_dir() else []:
        stale.unlink(missing_ok=True)
    atomic_write(out / SUMMARY, {"started": time.time(), "updated": time.time(), "workers_planned": workers, "units": units,
                                 "clips_total": sum(u["total"] for u in units), "running": True})


def eta_seconds(remaining: int, workers: list[dict]) -> float | None:
    """Remaining clips over the live workers' combined throughput, from each one's recent clip times."""
    rate = 0.0
    for w in workers:
        if w.get("finished") or not pid_alive(w.get("pid")):
            continue
        times = [t for t in (w.get("recent_clip_seconds") or []) if t and t > 0]
        if times:
            rate += 1.0 / (sum(times) / len(times))
    return remaining / rate if rate > 0 and remaining > 0 else (0.0 if remaining <= 0 else None)


def human(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    s = int(seconds)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def lock_holder() -> str | None:
    """Who holds the GPU lock, from gs_run.sh's owner file (pid id name start priority); None when free or stale."""
    lock = Path(os.environ.get("GS_GPU_LOCK") or Path.home() / ".gs-gpu.lock")
    owner = lock.with_name(lock.name + ".owner")
    try:
        parts = owner.read_text(encoding="utf-8").split()
    except OSError:
        return None
    if len(parts) >= 3 and parts[0].isdigit() and pid_alive(int(parts[0])):
        return f"held by '{parts[2]}' (pid {parts[0]}, {parts[4] if len(parts) > 4 else 'interactive'})"
    return None


def bar(done: int, total: int, width: int = 24) -> str:
    frac = 0.0 if total <= 0 else min(1.0, done / total)
    filled = int(round(frac * width))
    return "[" + "#" * filled + "-" * (width - filled) + f"] {int(frac * 100):3d}%"
