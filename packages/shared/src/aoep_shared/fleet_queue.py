"""Durable per-machine job queue for the Salareen fleet (Mac, iBuyPower, DGX Spark).

Stdlib only. One SQLite file per machine (default ~/.gs-queue/queue.db). There is deliberately
no shared database between machines: a machine keeps working through a network outage, and the
only cross-machine coordination is deterministic sharding (same input, same answer on every
machine), so two machines never do the same work.

Concepts
  JobType   what a job is (command template, resource class gpu|cpu|net, which machines may run
            it, priority, time window, retry policy). Loaded from scripts/fleet/jobs/*.json.
  Job       one row: queued -> leased -> running -> done | queued again (retry/preempt) | dead.
  Lease     a worker owns a job only while it keeps heartbeating. If the worker dies, the lease
            expires and the job goes back to the queue. Nothing is ever lost or run twice.

Nothing here starts a process. fleet_worker.py does that, through scripts/gs_run.sh.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

RESOURCES = ("gpu", "cpu", "net")
ACTIVE_STATES = ("queued", "leased", "running")
NON_RETRYABLE_EXIT = {64, 78}  # bad usage / configuration error: retrying cannot help
DEFER_EXIT = 75  # gs_run: not enough free memory, or the GPU lock is busy. Not the job's fault.
DEFAULT_LEASE_TTL_S = 120
MAX_BACKOFF_S = 6 * 3600
DEFAULT_TZ = "America/Los_Angeles"
_WINDOW_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class ConfigError(ValueError):
    """A manifest or a job's parameters cannot be turned into a command."""


# --------------------------------------------------------------------------------------------
# Job types and the manifest
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class JobType:
    name: str
    resource: str = "cpu"
    roles: tuple[str, ...] = ()  # machine keys allowed to run it; empty = any
    priority: int = 50  # 0..100, higher wins the GPU / the claim order
    cmd: tuple[str, ...] = ()
    gs_args: tuple[str, ...] = ()
    timeout_s: int | None = None
    max_attempts: int = 3
    backoff_s: int = 300
    preemptible: bool = False  # safe to stop and rerun later (the command must be resumable)
    needs_cuda: bool = False  # refuse to start unless the CUDA policy check passes
    window: tuple[str, str] | None = None  # (start, end) "HH:MM" in `tz`; may wrap midnight
    tz: str = DEFAULT_TZ
    fill: bool = False  # keep one instance queued per machine whenever none is active
    every_s: int = 0  # >0: enqueue one instance per period (dedupe bucket)
    shards: int = 0  # >0: one job per shard, pinned to a machine by machine_for_shard
    min_free_gb: float | None = None
    env: Mapping[str, str] = field(default_factory=dict)  # extra environment for the job ({placeholders} allowed)
    defaults: Mapping[str, Any] = field(default_factory=dict)
    machine_params: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    description: str = ""

    @staticmethod
    def from_dict(raw: Mapping[str, Any]) -> "JobType":
        name = str(raw.get("name", "")).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", name):
            raise ConfigError(f"bad job type name {name!r}")
        resource = raw.get("resource", "cpu")
        if resource not in RESOURCES:
            raise ConfigError(f"{name}: resource must be one of {RESOURCES}")
        cmd = raw.get("cmd") or []
        if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
            raise ConfigError(f"{name}: cmd must be a non-empty list of strings (no shell)")
        priority = int(raw.get("priority", 50))
        if not 0 <= priority <= 100:
            raise ConfigError(f"{name}: priority must be 0..100")
        window = raw.get("window")
        if window is not None:
            if not (isinstance(window, list) and len(window) == 2 and all(_WINDOW_RE.match(str(w)) for w in window)):
                raise ConfigError(f"{name}: window must be [\"HH:MM\", \"HH:MM\"]")
            window = (str(window[0]), str(window[1]))
        gs_args = raw.get("gs_args") or []
        if not isinstance(gs_args, list) or not all(isinstance(a, str) for a in gs_args):
            raise ConfigError(f"{name}: gs_args must be a list of strings")
        if resource == "gpu" and "--gpu" in gs_args:
            raise ConfigError(f"{name}: do not put --gpu in gs_args; resource=gpu adds it")
        return JobType(
            name=name,
            resource=resource,
            roles=tuple(raw.get("roles") or ()),
            priority=priority,
            cmd=tuple(cmd),
            gs_args=tuple(gs_args),
            timeout_s=int(raw["timeout_s"]) if raw.get("timeout_s") else None,
            max_attempts=max(1, int(raw.get("max_attempts", 3))),
            backoff_s=max(10, int(raw.get("backoff_s", 300))),
            preemptible=bool(raw.get("preemptible", False)),
            needs_cuda=bool(raw.get("needs_cuda", False)),
            window=window,
            tz=str(raw.get("tz", DEFAULT_TZ)),
            fill=bool(raw.get("fill", False)),
            every_s=int(raw.get("every_s", 0)),
            shards=int(raw.get("shards", 0)),
            min_free_gb=float(raw["min_free_gb"]) if raw.get("min_free_gb") is not None else None,
            env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
            defaults=dict(raw.get("defaults") or {}),
            machine_params={k: dict(v) for k, v in (raw.get("machine_params") or {}).items()},
            description=str(raw.get("description", "")),
        )

    def allowed_on(self, machine: str) -> bool:
        return not self.roles or machine in self.roles

    def params_for(self, machine: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        merged: dict[str, Any] = dict(self.defaults)
        merged.update(self.machine_params.get(machine, {}))
        merged.update(payload or {})
        return merged


def render_cmd(spec: JobType, payload: Mapping[str, Any], machine: str, repo: str, home: str, day: str,
               extra: Mapping[str, Any] | None = None) -> list[str]:
    """Fill {placeholders}. A placeholder with no value is a ConfigError, never a literal brace."""
    values: dict[str, Any] = spec.params_for(machine, payload)
    values.update({"repo": repo, "machine": machine, "home": home, "day": day})
    values.update(extra or {})
    out: list[str] = []
    for token in spec.cmd:
        def sub(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in values:
                raise ConfigError(f"{spec.name}: no value for {{{key}}} (payload {sorted(payload)})")
            return str(values[key])
        out.append(_PLACEHOLDER.sub(sub, token))
    return out


def render_env(spec: JobType, payload: Mapping[str, Any], machine: str, repo: str, home: str, day: str,
               extra: Mapping[str, Any] | None = None) -> dict[str, str]:
    tmp = JobType(name=spec.name, cmd=tuple(spec.env.values()) or ("x",), defaults=spec.defaults, machine_params=spec.machine_params)
    if not spec.env:
        return {}
    rendered = render_cmd(tmp, payload, machine, repo, home, day, extra)
    return dict(zip(spec.env.keys(), rendered))


def load_manifest(directory: str | Path) -> tuple[dict[str, JobType], dict[str, dict[str, int]], dict[str, Any]]:
    """Read *.json job types plus _caps.json. Returns (types, caps, settings_defaults)."""
    root = Path(directory)
    types: dict[str, JobType] = {}
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            spec = JobType.from_dict(json.loads(path.read_text()))
        except (json.JSONDecodeError, ConfigError) as exc:
            raise ConfigError(f"{path.name}: {exc}") from exc
        if spec.name in types:
            raise ConfigError(f"duplicate job type {spec.name}")
        types[spec.name] = spec
    caps: dict[str, dict[str, int]] = {}
    extra: dict[str, Any] = {}
    caps_file = root / "_caps.json"
    if caps_file.exists():
        raw = json.loads(caps_file.read_text())
        extra = {k: v for k, v in raw.items() if k != "caps"}
        for machine, per in (raw.get("caps") or {}).items():
            caps[machine] = {r: int(per.get(r, 0)) for r in RESOURCES}
    return types, caps, extra


# --------------------------------------------------------------------------------------------
# Time windows and sharding (pure)
# --------------------------------------------------------------------------------------------
def _minutes(hhmm: str) -> int:
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def local_minutes(now: float, tz: str) -> int:
    """Minutes since midnight in tz. Falls back to UTC if tz data is missing (never raises)."""
    try:
        from zoneinfo import ZoneInfo

        dt = datetime.fromtimestamp(now, ZoneInfo(tz))
    except Exception:
        dt = datetime.fromtimestamp(now, timezone.utc)
    return dt.hour * 60 + dt.minute


def in_window(window: tuple[str, str] | None, now: float, tz: str = DEFAULT_TZ) -> bool:
    """True if now is inside [start, end). Handles windows that wrap midnight (22:00-07:00)."""
    if window is None:
        return True
    start, end = _minutes(window[0]), _minutes(window[1])
    cur = local_minutes(now, tz)
    if start == end:
        return True
    return start <= cur < end if start < end else (cur >= start or cur < end)


def day_stamp(now: float, tz: str = DEFAULT_TZ) -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.fromtimestamp(now, ZoneInfo(tz)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")


def shard_for(key: str, nshards: int) -> int:
    """Deterministic shard of a key (sha256, not Python's salted hash): identical on every machine."""
    if nshards <= 1:
        return 0
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % nshards


def machine_for_shard(shard: int, machines: Iterable[str]) -> str:
    """Which machine owns a shard. Sorted so every machine computes the same assignment."""
    ordered = sorted(set(machines))
    if not ordered:
        raise ConfigError("no machines for sharding")
    return ordered[shard % len(ordered)]


def host_of(url: str) -> str:
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://([^/:?#]+)", url.strip())
    return (m.group(1) if m else url.strip()).lower()


def shard_of_url(url: str, nshards: int) -> int:
    """Shard by HOST, not by URL: one machine crawls a given site, which keeps rate limits polite."""
    return shard_for(host_of(url), nshards)


def backoff_seconds(spec_backoff: int, attempts: int, job_id: int) -> int:
    base = min(MAX_BACKOFF_S, spec_backoff * (2 ** max(0, attempts - 1)))
    jitter = (job_id * 2654435761) % max(1, base // 5 + 1)  # deterministic, spreads retries
    return int(base + jitter)


# --------------------------------------------------------------------------------------------
# The queue
# --------------------------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  resource TEXT NOT NULL,
  dedupe_key TEXT,
  payload TEXT NOT NULL DEFAULT '{}',
  state TEXT NOT NULL DEFAULT 'queued',
  priority INTEGER NOT NULL DEFAULT 50,
  machine TEXT,
  leased_by TEXT,
  lease_expires REAL,
  heartbeat REAL,
  runner_pid INTEGER,
  runner_start TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  not_before REAL NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  started REAL,
  finished REAL,
  exit_code INTEGER,
  error TEXT NOT NULL DEFAULT '',
  preempted INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_dedupe ON jobs(dedupe_key)
  WHERE dedupe_key IS NOT NULL AND state IN ('queued','leased','running');
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state, priority DESC, id);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class Queue:
    def __init__(self, path: str | Path, clock: Callable[[], float] = time.time):
        self.path = str(path)
        self.clock = clock
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript(_SCHEMA)

    def close(self) -> None:
        self.db.close()

    # -- tiny transaction helper ---------------------------------------------------------
    def _tx(self):
        return _Tx(self.db)

    # -- settings ------------------------------------------------------------------------
    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set_setting(self, key: str, value: Any) -> None:
        self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value)))

    def disabled_types(self) -> set[str]:
        return set(self.get_setting("disabled_types", []))

    def paused(self) -> bool:
        return bool(self.get_setting("paused", False))

    # -- enqueue -------------------------------------------------------------------------
    def enqueue(self, spec: JobType, payload: Mapping[str, Any] | None = None, *, dedupe_key: str | None = None,
                priority: int | None = None, machine: str | None = None, not_before: float = 0.0) -> int | None:
        """Add a job. Returns its id, or None if an active job already has this dedupe key."""
        now = self.clock()
        try:
            cur = self.db.execute(
                "INSERT INTO jobs(type,resource,dedupe_key,payload,priority,machine,max_attempts,not_before,created)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (spec.name, spec.resource, dedupe_key, json.dumps(dict(payload or {}), sort_keys=True),
                 spec.priority if priority is None else priority, machine, spec.max_attempts, not_before, now),
            )
        except sqlite3.IntegrityError:
            return None
        return int(cur.lastrowid)

    def get(self, job_id: int) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    # -- claiming ------------------------------------------------------------------------
    def _active_counts(self, machine_worker: str) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT resource, COUNT(*) n FROM jobs WHERE state IN ('leased','running') GROUP BY resource").fetchall()
        return {r["resource"]: r["n"] for r in rows}

    def eligible(self, row: Mapping[str, Any], machine: str, types: Mapping[str, JobType], now: float,
                 disabled: set[str]) -> JobType | None:
        spec = types.get(row["type"])
        if spec is None or row["type"] in disabled or not spec.allowed_on(machine):
            return None
        if row["machine"] not in (None, machine):
            return None
        if not in_window(spec.window, now, spec.tz):
            return None
        return spec

    def claim(self, worker_id: str, machine: str, types: Mapping[str, JobType], caps: Mapping[str, int],
              ttl: int = DEFAULT_LEASE_TTL_S, skip_resources: Iterable[str] = ()) -> dict[str, Any] | None:
        """Lease the best eligible queued job, honoring per-resource concurrency caps. One at a time."""
        if self.paused():
            return None
        now = self.clock()
        disabled = self.disabled_types()
        skip = set(skip_resources)
        with self._tx():
            active = self._active_counts(worker_id)
            rows = self.db.execute(
                "SELECT * FROM jobs WHERE state='queued' AND not_before<=? ORDER BY priority DESC, id ASC", (now,)).fetchall()
            for row in rows:
                spec = self.eligible(row, machine, types, now, disabled)
                if spec is None or row["resource"] in skip:
                    continue
                if active.get(row["resource"], 0) >= int(caps.get(row["resource"], 0)):
                    continue
                attempts = row["attempts"] + (0 if row["preempted"] else 1)
                self.db.execute(
                    "UPDATE jobs SET state='leased', leased_by=?, lease_expires=?, heartbeat=?, attempts=?, preempted=0,"
                    " started=?, error='' WHERE id=?", (worker_id, now + ttl, now, attempts, now, row["id"]))
                return self.get(row["id"])
        return None

    def mark_running(self, job_id: int, worker_id: str, runner_pid: int, runner_start: str) -> bool:
        cur = self.db.execute("UPDATE jobs SET state='running', runner_pid=?, runner_start=? WHERE id=? AND leased_by=?"
                              " AND state IN ('leased','running')", (runner_pid, runner_start, job_id, worker_id))
        return cur.rowcount == 1

    def heartbeat(self, job_id: int, worker_id: str, ttl: int = DEFAULT_LEASE_TTL_S) -> bool:
        """Renew the lease. False means the lease was lost: the worker must stop the job."""
        now = self.clock()
        cur = self.db.execute("UPDATE jobs SET heartbeat=?, lease_expires=? WHERE id=? AND leased_by=?"
                              " AND state IN ('leased','running')", (now, now + ttl, job_id, worker_id))
        return cur.rowcount == 1

    # -- finishing -----------------------------------------------------------------------
    def finish(self, job_id: int, worker_id: str, exit_code: int, spec: JobType | None, error: str = "") -> str:
        """Record the outcome. Returns the new state: done | queued (retry or defer) | dead."""
        now = self.clock()
        with self._tx():
            row = self.db.execute("SELECT * FROM jobs WHERE id=? AND leased_by=?", (job_id, worker_id)).fetchone()
            if row is None or row["state"] not in ("leased", "running"):
                return "lost"
            base = {"finished": now, "exit_code": exit_code, "leased_by": None, "lease_expires": None,
                    "runner_pid": None, "runner_start": None}
            if exit_code == 0:
                return self._set(job_id, "done", base, error="")
            if exit_code == DEFER_EXIT:
                # gs_run refused (low memory / GPU lock busy): try again later, and do not count an attempt.
                self.db.execute("UPDATE jobs SET attempts=MAX(0,attempts-1) WHERE id=?", (job_id,))
                nb = now + 300 + backoff_seconds(60, 1, job_id)
                return self._set(job_id, "queued", {**base, "not_before": nb, "finished": None},
                                 error=error or "deferred: not enough free memory or the GPU lock is busy")
            if exit_code in NON_RETRYABLE_EXIT:
                return self._set(job_id, "dead", base, error=error or f"exit {exit_code}: configuration error, not retried")
            max_attempts = row["max_attempts"]
            if row["attempts"] >= max_attempts:
                return self._set(job_id, "dead", base, error=error or f"exit {exit_code} after {row['attempts']} attempts")
            backoff = backoff_seconds(spec.backoff_s if spec else 300, row["attempts"], job_id)
            return self._set(job_id, "queued", {**base, "not_before": now + backoff, "finished": None},
                             error=error or f"exit {exit_code}, retry in {backoff}s")

    def _set(self, job_id: int, state: str, fields: Mapping[str, Any], error: str) -> str:
        cols = dict(fields)
        cols["state"] = state
        cols["error"] = error
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*cols.values(), job_id))
        return state

    def release(self, job_id: int, worker_id: str, reason: str, delay_s: int = 60) -> bool:
        """Give a job back without blaming it (preempted, memory pressure, worker shutting down)."""
        now = self.clock()
        cur = self.db.execute(
            "UPDATE jobs SET state='queued', leased_by=NULL, lease_expires=NULL, runner_pid=NULL, runner_start=NULL,"
            " preempted=1, not_before=?, error=? WHERE id=? AND leased_by=? AND state IN ('leased','running')",
            (now + delay_s, reason, job_id, worker_id))
        return cur.rowcount == 1

    def reap_expired(self) -> list[dict[str, Any]]:
        """Return jobs whose lease ran out (their worker died or hung) to the queue, or kill them off
        if they already used every attempt. Returns what was reaped so the worker can log it and stop
        any runner process it left behind."""
        now = self.clock()
        reaped: list[dict[str, Any]] = []
        with self._tx():
            rows = self.db.execute("SELECT * FROM jobs WHERE state IN ('leased','running') AND lease_expires<?", (now,)).fetchall()
            for row in rows:
                reaped.append(dict(row))
                if row["attempts"] >= row["max_attempts"]:
                    self._set(row["id"], "dead", {"finished": now, "leased_by": None, "lease_expires": None,
                                                  "runner_pid": None, "runner_start": None},
                              error="lease expired (worker lost) after the last attempt")
                else:
                    self._set(row["id"], "queued", {"leased_by": None, "lease_expires": None, "runner_pid": None,
                                                    "runner_start": None, "not_before": now + 30},
                              error="lease expired (worker lost); requeued")
        return reaped

    def cancel(self, job_id: int) -> bool:
        cur = self.db.execute("UPDATE jobs SET state='cancelled', finished=?, leased_by=NULL, lease_expires=NULL WHERE id=?"
                              " AND state='queued'", (self.clock(), job_id))
        return cur.rowcount == 1

    def requeue(self, job_id: int) -> bool:
        cur = self.db.execute("UPDATE jobs SET state='queued', attempts=0, not_before=0, error='', finished=NULL"
                              " WHERE id=? AND state IN ('dead','failed','cancelled','done')", (job_id,))
        return cur.rowcount == 1

    def prune(self, keep_days: int = 30) -> int:
        cutoff = self.clock() - keep_days * 86400
        cur = self.db.execute("DELETE FROM jobs WHERE state IN ('done','dead','cancelled') AND finished<?", (cutoff,))
        return cur.rowcount

    # -- scheduling the work itself ----------------------------------------------------------
    def ensure_scheduled(self, types: Mapping[str, JobType], machine: str, machines_by_role: Mapping[str, list[str]],
                         now: float | None = None) -> list[int]:
        """Keep the queue stocked: fill jobs (always one waiting), periodic jobs (one per period) and
        shard jobs (one per shard, pinned to the machine that owns the shard). Idempotent."""
        now = self.clock() if now is None else now
        disabled = self.disabled_types()
        created: list[int] = []
        for spec in types.values():
            if spec.name in disabled or not spec.allowed_on(machine):
                continue
            if spec.shards > 0:
                eligible_machines = list(spec.roles) or [machine]
                day = day_stamp(now, spec.tz)
                for shard in range(spec.shards):
                    owner = machine_for_shard(shard, eligible_machines)
                    if owner != machine:
                        continue  # another machine creates its own shards; nobody crawls the same shard twice
                    key = f"{spec.name}:{day}:{shard}/{spec.shards}"
                    jid = self.enqueue(spec, {"shard": shard, "nshards": spec.shards}, dedupe_key=key, machine=machine)
                    if jid:
                        created.append(jid)
            elif spec.every_s > 0:
                bucket = int(now // spec.every_s)
                jid = self.enqueue(spec, {}, dedupe_key=f"{spec.name}:{machine}:{bucket}", machine=machine)
                if jid:
                    created.append(jid)
            elif spec.fill:
                jid = self.enqueue(spec, {}, dedupe_key=f"{spec.name}:fill:{machine}", machine=machine)
                if jid:
                    created.append(jid)
        return created

    # -- preemption ------------------------------------------------------------------------
    PREEMPT_MARGIN = 10

    def preemption_victim(self, machine: str, types: Mapping[str, JobType], caps: Mapping[str, int]) -> dict[str, Any] | None:
        """A running preemptible job that should make way for a clearly more important queued job
        needing the same (full) resource. Returns the running job row, or None."""
        now = self.clock()
        disabled = self.disabled_types()
        running = [dict(r) for r in self.db.execute("SELECT * FROM jobs WHERE state IN ('leased','running')").fetchall()]
        for resource in RESOURCES:
            cap = int(caps.get(resource, 0))
            on_res = [r for r in running if r["resource"] == resource]
            if cap <= 0 or len(on_res) < cap:
                continue
            queued = [dict(r) for r in self.db.execute(
                "SELECT * FROM jobs WHERE state='queued' AND resource=? AND not_before<=? ORDER BY priority DESC, id", (resource, now))]
            waiting = [q for q in queued if self.eligible(q, machine, types, now, disabled) is not None]
            if not waiting:
                continue
            top = waiting[0]
            victims = [r for r in on_res if (types.get(r["type"]) and types[r["type"]].preemptible)
                       and top["priority"] >= r["priority"] + self.PREEMPT_MARGIN]
            if victims:
                return min(victims, key=lambda r: (r["priority"], -r["id"]))
        return None

    def lowest_priority_preemptible(self, types: Mapping[str, JobType]) -> dict[str, Any] | None:
        rows = [dict(r) for r in self.db.execute("SELECT * FROM jobs WHERE state IN ('leased','running')").fetchall()]
        rows = [r for r in rows if types.get(r["type"]) and types[r["type"]].preemptible]
        return min(rows, key=lambda r: (r["priority"], -r["id"])) if rows else None

    # -- reporting ---------------------------------------------------------------------------
    def status(self, machine: str, types: Mapping[str, JobType], caps: Mapping[str, int] | None = None) -> dict[str, Any]:
        now = self.clock()
        disabled = self.disabled_types()
        counts = {r["state"]: r["n"] for r in self.db.execute("SELECT state, COUNT(*) n FROM jobs GROUP BY state")}
        running = [{"id": r["id"], "type": r["type"], "started": r["started"], "runner_pid": r["runner_pid"],
                    "priority": r["priority"], "resource": r["resource"]}
                   for r in self.db.execute("SELECT * FROM jobs WHERE state IN ('leased','running') ORDER BY id")]
        queued = self.db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY priority DESC, id").fetchall()
        eligible_now, blocked = [], {}
        for row in queued:
            spec = types.get(row["type"])
            if spec is None:
                blocked["unknown-type"] = blocked.get("unknown-type", 0) + 1
            elif row["type"] in disabled:
                blocked["disabled"] = blocked.get("disabled", 0) + 1
            elif not spec.allowed_on(machine) or row["machine"] not in (None, machine):
                blocked["other-machine"] = blocked.get("other-machine", 0) + 1
            elif not in_window(spec.window, now, spec.tz):
                blocked["outside-window"] = blocked.get("outside-window", 0) + 1
            elif row["not_before"] > now:
                blocked["backing-off"] = blocked.get("backing-off", 0) + 1
            else:
                eligible_now.append(row["type"])
        stale = self.db.execute("SELECT COUNT(*) n FROM jobs WHERE state IN ('leased','running') AND lease_expires<?", (now,)).fetchone()["n"]
        last_success = {r["type"]: r["t"] for r in self.db.execute(
            "SELECT type, MAX(finished) t FROM jobs WHERE state='done' GROUP BY type")}
        dead_24h = [{"id": r["id"], "type": r["type"], "error": r["error"][:160]} for r in self.db.execute(
            "SELECT * FROM jobs WHERE state='dead' AND finished>? ORDER BY finished DESC LIMIT 10", (now - 86400,))]
        oldest = min((row["created"] for row in queued if row["type"] in eligible_now), default=None)
        return {
            "machine": machine,
            "now": now,
            "counts": counts,
            "running": running,
            "queued_eligible": len(eligible_now),
            "queued_blocked": blocked,
            "oldest_eligible_age_s": int(now - oldest) if oldest else 0,
            "stale_leases": stale,
            "last_success": last_success,
            "dead_24h": dead_24h,
            "paused": self.paused(),
            "disabled": sorted(disabled),
            "caps": dict(caps or {}),
            "worker": self.get_setting("worker_state", {}),
            "last_busy": self.get_setting("last_busy", 0),
        }


class _Tx:
    """BEGIN IMMEDIATE ... COMMIT, so claim/finish are atomic even with a CLI running beside the worker."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def __enter__(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type, exc, tb) -> None:
        self.db.execute("ROLLBACK" if exc_type else "COMMIT")
