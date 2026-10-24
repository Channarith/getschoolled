"""Run slow work in the background so an HTTP request never waits on it.

POST handlers call ``runner.submit(...)`` and answer 202 with a job id at once;
clients poll ``GET <prefix>/{job_id}``. Gateways and browsers give up on
requests that take about 30 seconds, so anything that can run longer belongs here.

Bounded concurrency (thread pool), duplicate submits join the running job, and
every state change is written to ``store_dir`` (when given) so a result survives
a client disconnect and a restart. Errors never become a 5xx: a failed job
carries a ``code`` and a friendly ``message``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("aoep.background_jobs")

ACTIVE = ("queued", "running")
FRIENDLY_FAILURE = "That took a hiccup on our side. Please try again in a moment."


class JobError(Exception):
    """Raise inside a job for an expected failure with a stable code and message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def payload_key(kind: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return f"{kind}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


class JobRunner:
    def __init__(
        self,
        *,
        max_workers: int = 2,
        ttl_seconds: int = 6 * 3600,
        max_jobs: int = 300,
        store_dir: Optional[Path | str] = None,
    ) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="bgjob")
        self._ttl = ttl_seconds
        self._max_jobs = max_jobs
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._store = Path(store_dir) if store_dir else None

    def submit(
        self,
        kind: str,
        fn: Callable[[Callable[[float, str], None]], Any],
        *,
        key: Optional[str] = None,
        exclusive: bool = False,
    ) -> dict[str, Any]:
        """Queue ``fn(report)``; returns the job snapshot immediately.

        A submit with the same ``key`` (or any active job of the same ``kind`` when
        ``exclusive``) joins the job already running instead of starting another.
        """
        with self._lock:
            self._prune()
            for job in self._jobs.values():
                if job["state"] not in ACTIVE:
                    continue
                if (key and job.get("key") == key) or (exclusive and job["kind"] == kind):
                    return {**self._public(job), "joined": True}
            job_id = uuid.uuid4().hex[:16]
            job = {
                "job_id": job_id,
                "kind": kind,
                "key": key,
                "state": "queued",
                "progress": 0.0,
                "message": "Queued",
                "created_at": time.time(),
                "started_at": None,
                "finished_at": None,
                "result": None,
                "error": None,
            }
            self._jobs[job_id] = job
            self._persist(job)
            snapshot = self._public(job)
        self._pool.submit(self._run, job_id, fn)
        return snapshot

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                return self._public(job)
        return self._load(job_id)

    def _run(self, job_id: str, fn: Callable[[Callable[[float, str], None]], Any]) -> None:
        def report(fraction: float, message: str = "") -> None:
            with self._lock:
                job = self._jobs.get(job_id)
                if job and job["state"] == "running":
                    job["progress"] = max(0.0, min(1.0, float(fraction)))
                    if message:
                        job["message"] = message

        with self._lock:
            job = self._jobs[job_id]
            job["state"] = "running"
            job["started_at"] = time.time()
            job["message"] = "Working"
            self._persist(job)
        try:
            result = fn(report)
            outcome: dict[str, Any] = {"state": "done", "progress": 1.0, "message": "Done", "result": result}
        except JobError as exc:
            outcome = {"state": "failed", "error": {"code": exc.code, "message": exc.message}, "message": exc.message}
        except Exception:  # noqa: BLE001 - a job failure must never escape the worker
            log.exception("background job %s failed", job_id)
            outcome = {
                "state": "failed",
                "error": {"code": "internal", "message": FRIENDLY_FAILURE},
                "message": FRIENDLY_FAILURE,
            }
        with self._lock:
            job = self._jobs[job_id]
            job.update(outcome)
            job["finished_at"] = time.time()
            self._persist(job)

    def _public(self, job: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in job.items() if k != "key"}
        out["elapsed_seconds"] = round((job["finished_at"] or time.time()) - job["created_at"], 2)
        return out

    def _prune(self) -> None:
        now = time.time()
        stale = [
            jid for jid, j in self._jobs.items()
            if j["state"] not in ACTIVE and now - (j["finished_at"] or now) > self._ttl
        ]
        for jid in stale:
            del self._jobs[jid]
        if len(self._jobs) > self._max_jobs:
            done = sorted(
                (j for j in self._jobs.values() if j["state"] not in ACTIVE),
                key=lambda j: j["finished_at"] or 0,
            )
            for j in done[: len(self._jobs) - self._max_jobs]:
                del self._jobs[j["job_id"]]

    def _path(self, job_id: str) -> Optional[Path]:
        if not self._store or not job_id.isalnum():
            return None
        return self._store / f"{job_id}.json"

    def _persist(self, job: dict[str, Any]) -> None:
        path = self._path(job["job_id"])
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(job, default=str), encoding="utf-8")
            os.replace(tmp, path)
        except OSError:
            log.warning("could not persist job %s", job["job_id"])

    def _load(self, job_id: str) -> Optional[dict[str, Any]]:
        path = self._path(job_id)
        if path is None or not path.is_file():
            return None
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if job.get("state") in ACTIVE:
            job.update(
                state="failed",
                message="This job was interrupted by a restart. Please run it again.",
                error={"code": "interrupted", "message": "This job was interrupted by a restart. Please run it again."},
            )
        job.pop("key", None)
        job.setdefault("elapsed_seconds", 0)
        return job


def accepted_response(snapshot: dict[str, Any], status_path: str):
    """The 202 a POST returns: job state plus where to poll."""
    from fastapi.responses import JSONResponse

    body = {**snapshot, "status_url": f"{status_path.rstrip('/')}/{snapshot['job_id']}"}
    return JSONResponse(body, status_code=202, headers={"Location": body["status_url"], "Retry-After": "2"})


def install_job_status_route(app, runner: JobRunner, path: str) -> None:
    """Add ``GET <path>/{job_id}``; an unknown id is a friendly 404 body, never a 5xx."""
    from fastapi.responses import JSONResponse

    @app.get(path.rstrip("/") + "/{job_id}")
    def job_status(job_id: str):
        job = runner.get(job_id)
        if job is None:
            return JSONResponse(
                {"state": "unknown", "error": {"code": "not_found", "message": "We could not find that job. It may have expired; please start it again."}},
                status_code=404,
            )
        return job
