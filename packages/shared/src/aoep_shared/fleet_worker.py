"""gs_worker: the loop that keeps a machine busy with the right work, safely.

Each tick it
  1. renews the lease of every job it runs (a hung or dead worker loses its jobs to the queue),
  2. reaps finished processes (no zombies: every child is poll()ed or wait()ed),
  3. steps aside for a clearly more important job (preemption) or for memory pressure,
  4. stocks the queue (fill / periodic / sharded jobs),
  5. claims new work if the machine has room, behind the safety gates below.

Safety rules (all enforced here, all covered by tests)
  * never more than one GPU job per machine (queue cap AND the gs_run GPU lock),
  * a GPU job on the Spark does not start unless the CUDA policy check passes,
  * only processes THIS worker started are ever signalled (recorded runner pid + start time + the
    gsq-<id>- name in its command line), never anything else on the machine,
  * every job goes through scripts/gs_run.sh, so memory/CPU limits and whole-tree cleanup apply,
  * on memory pressure the lowest-priority preemptible job is STOPPED and requeued (SIGSTOP would
    not free any RAM), and it resumes later; non-resumable jobs are never touched.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .fleet_queue import (
    ConfigError,
    DEFAULT_LEASE_TTL_S,
    JobType,
    Queue,
    day_stamp,
    render_cmd,
    render_env,
)

KILL_GRACE_S = 30
PRESSURE_FRACTION = 0.75  # stop work when available memory falls below 75% of the reserve
PRESSURE_TICKS = 2  # ...for this many ticks in a row
CUDA_CACHE_S = 600


# --------------------------------------------------------------------------------------------
# Process handling
# --------------------------------------------------------------------------------------------
class Handle(Protocol):
    pid: int
    start_token: str

    def poll(self) -> int | None: ...
    def terminate(self, grace_s: float = KILL_GRACE_S) -> int: ...


def process_start_token(pid: int) -> str:
    """Something that changes if a pid is reused: /proc start time on Linux, `ps lstart` elsewhere."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.rsplit(")", 1)[1].split()[19]  # field 22: starttime
    except Exception:
        pass
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
        return " ".join(out.split())
    except Exception:
        return ""


def process_cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except Exception:
        pass
    try:
        return subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""


def pid_is_ours(pid: int | None, token: str | None, job_id: int) -> bool:
    """True only if pid is alive, is the same process we recorded, and is a gs_run for this job id."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    if token and process_start_token(pid) not in ("", token):
        return False
    return f"gsq-{job_id}-" in process_cmdline(pid)


def process_is_dead(pid: int) -> bool:
    """Gone, or a zombie (dead but not yet reaped by its parent, which counts as dead for our purposes)."""
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return state == "Z"
    except Exception:
        pass
    try:
        out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout.strip()
        return out == "" or out.startswith("Z")
    except Exception:
        return False


def _signal_group_until(pgid: int, pid: int, sig: int, wait_s: float, is_dead) -> bool:
    try:
        os.killpg(pgid, sig)
    except OSError:
        return True
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if is_dead(pid):
            return True
        time.sleep(0.1)
    return is_dead(pid)


def kill_group(pid: int, grace_s: float = KILL_GRACE_S) -> None:
    """SIGTERM the whole process group (gs_run traps it and tears down its job tree), then SIGKILL."""
    try:
        pgid = os.getpgid(pid)
    except OSError:
        return
    if not _signal_group_until(pgid, pid, signal.SIGTERM, grace_s, process_is_dead):
        _signal_group_until(pgid, pid, signal.SIGKILL, 5, process_is_dead)


class SubprocessHandle:
    def __init__(self, popen: subprocess.Popen):
        self._p = popen
        self.pid = popen.pid
        self.start_token = process_start_token(popen.pid)

    def poll(self) -> int | None:
        return self._p.poll()  # also reaps the child: no zombie

    def terminate(self, grace_s: float = KILL_GRACE_S) -> int:
        """Stop the group and REAP the child (poll/wait), so it never lingers as a zombie."""
        if self._p.poll() is None:
            try:
                pgid = os.getpgid(self._p.pid)
            except OSError:
                pgid = None
            if pgid is not None:
                if not _signal_group_until(pgid, self._p.pid, signal.SIGTERM, grace_s, lambda _pid: self._p.poll() is not None):
                    _signal_group_until(pgid, self._p.pid, signal.SIGKILL, 5, lambda _pid: self._p.poll() is not None)
        try:
            return self._p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            return -9


class SubprocessRunner:
    def start(self, argv: list[str], env: Mapping[str, str], cwd: str, log_path: str) -> Handle:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log = open(log_path, "ab", buffering=0)
        popen = subprocess.Popen(argv, env=dict(env), cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, start_new_session=True)
        log.close()
        return SubprocessHandle(popen)


# --------------------------------------------------------------------------------------------
# Machine facts and gates
# --------------------------------------------------------------------------------------------
def mem_available_gb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1048576
    except Exception:
        pass
    try:  # macOS
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=5).stdout
        page = 4096
        pages = 0
        for line in out.splitlines():
            if "page size of" in line:
                page = int(line.split("page size of")[1].split()[0])
            elif line.split(":")[0] in ("Pages free", "Pages inactive", "Pages speculative"):
                pages += int(line.split(":")[1].strip().rstrip("."))
        return pages * page / 1073741824
    except Exception:
        return 1e9  # unknown: do not block the machine on a probe failure


def gpu_lock_free(path: str) -> bool:
    """True if nobody holds the GPU lock right now (we try it without waiting and let go)."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    except OSError:
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


_CUDA_SCRIPT = r"""
import sys
try:
    import aoep_shared.devices as d
except Exception:
    d = None
if d is not None and callable(getattr(d, "cuda_smoke", None)):
    ok, detail = d.cuda_smoke()  # the CUDA policy's own check: real kernels, not just is_available()
    print(("ok " if ok else "FAIL ") + str(detail))
    sys.exit(0 if ok else 3)
import torch
if not torch.cuda.is_available():
    print("torch.cuda.is_available() is False (torch %s)" % torch.__version__); sys.exit(3)
a = torch.randn(256, 256, device="cuda"); b = (a @ a).sum().item()
print("ok torch %s cuda %s %s" % (torch.__version__, torch.version.cuda, torch.cuda.get_device_name(0)))
"""


def find_python(repo: str, home: str, env: Mapping[str, str] | None = None) -> str:
    env = env or os.environ
    candidates = [env.get("GS_PYTHON", ""), f"{repo}/.venv/bin/python", f"{home}/code/getschoolled/.venv/bin/python",
                  f"{home}/getschoolled/.venv/bin/python"]
    for c in candidates:
        if c and os.access(c, os.X_OK):
            return c
    return sys.executable or "python3"


def default_cuda_check(python: str, repo: str) -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{repo}/packages/shared/src:" + env.get("PYTHONPATH", "")
    try:
        r = subprocess.run([python, "-c", _CUDA_SCRIPT], capture_output=True, text=True, timeout=45, env=env, cwd=repo)
    except subprocess.TimeoutExpired:
        return False, "CUDA check timed out after 45s"
    except OSError as exc:
        return False, f"cannot run {python}: {exc}"
    detail = r.stdout.strip() or (r.stderr.strip().splitlines() or [""])[-1]
    return r.returncode == 0, detail[:200]


def sd_notify(message: str) -> None:
    """systemd Type=notify keep-alive (READY=1, WATCHDOG=1). A no-op when not run by systemd."""
    path = os.environ.get("NOTIFY_SOCKET")
    if not path:
        return
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect("\0" + path[1:] if path.startswith("@") else path)
        sock.sendall(message.encode())
        sock.close()
    except OSError:
        pass


# --------------------------------------------------------------------------------------------
# The worker
# --------------------------------------------------------------------------------------------
@dataclass
class WorkerConfig:
    machine: str
    repo: str
    home: str
    python: str
    caps: Mapping[str, int]
    reserve_mem_gb: float = 4.0
    cuda_required: bool = False  # True on the Spark: GPU work must use CUDA, never silently CPU
    gpu_lock: str = ""
    logs_dir: str = ""
    lease_ttl: int = DEFAULT_LEASE_TTL_S
    schedule_every_s: int = 60
    machines_by_role: Mapping[str, list[str]] = field(default_factory=dict)
    state_dir: str = ""  # queue db, logs and job work files; default ~/.gs-queue
    hostname: str = field(default_factory=lambda: socket.gethostname().split(".")[0])


@dataclass
class Running:
    job: dict[str, Any]
    spec: JobType
    handle: Handle
    started: float


class Worker:
    def __init__(self, queue: Queue, types: Mapping[str, JobType], cfg: WorkerConfig, runner: Any,
                 now: Callable[[], float] = time.time, mem_avail: Callable[[], float] = mem_available_gb,
                 cuda_check: Callable[[], tuple[bool, str]] | None = None,
                 lock_free: Callable[[], bool] | None = None, notify: Callable[[str], None] = sd_notify,
                 log: Callable[[str], None] | None = None):
        self.q, self.types, self.cfg, self.runner = queue, types, cfg, runner
        self.now, self.mem_avail, self.notify = now, mem_avail, notify
        self.cuda_check = cuda_check or (lambda: default_cuda_check(cfg.python, cfg.repo))
        self.lock_free = lock_free or (lambda: gpu_lock_free(cfg.gpu_lock or f"{cfg.home}/.gs-gpu.lock"))
        self.log = log or (lambda m: print(f"{time.strftime('%F %T')} gs_worker {m}", flush=True))
        self.worker_id = f"{cfg.machine}:{cfg.hostname}:{os.getpid()}"
        self.running: dict[int, Running] = {}
        self._pressure = 0
        self._last_sched = 0.0
        self._cuda_cache: tuple[float, tuple[bool, str]] | None = None
        self.blocked = ""

    # -- start-up and shutdown ---------------------------------------------------------------
    def recover(self) -> int:
        """After a crash or restart: stop any runner a previous incarnation of this worker left behind
        (only ones we can positively identify), then give their jobs back to the queue."""
        prefix = f"{self.cfg.machine}:{self.cfg.hostname}:"
        n = 0
        for row in self.q.db.execute("SELECT * FROM jobs WHERE state IN ('leased','running')").fetchall():
            owner = row["leased_by"] or ""
            if not owner.startswith(prefix) or owner == self.worker_id or row["id"] in self.running:
                continue
            if pid_is_ours(row["runner_pid"], row["runner_start"], row["id"]):
                self.log(f"recover: stopping leftover runner pid {row['runner_pid']} of job {row['id']} ({row['type']})")
                kill_group(row["runner_pid"])
            if self.q.release(row["id"], owner, "worker restarted; job returned to the queue", delay_s=30):
                n += 1
        return n

    def shutdown(self) -> None:
        for job_id, run in list(self.running.items()):
            self.log(f"shutdown: stopping job {job_id} ({run.spec.name})")
            run.handle.terminate(KILL_GRACE_S)
            self.q.release(job_id, self.worker_id, "worker stopping; job returned to the queue", delay_s=30)
            del self.running[job_id]

    # -- gates --------------------------------------------------------------------------------
    def _cuda_ok(self) -> tuple[bool, str]:
        t = self.now()
        if self._cuda_cache and t - self._cuda_cache[0] < CUDA_CACHE_S and self._cuda_cache[1][0]:
            return self._cuda_cache[1]
        if self._cuda_cache and t - self._cuda_cache[0] < 120 and not self._cuda_cache[1][0]:
            return self._cuda_cache[1]  # do not hammer a broken GPU with a check every tick
        result = self.cuda_check()
        self._cuda_cache = (t, result)
        return result

    # -- one tick -----------------------------------------------------------------------------
    def tick(self) -> None:
        now = self.now()
        self.notify("WATCHDOG=1")
        self._reap_expired()
        self._finalize_finished()
        self._heartbeat()
        self._memory_pressure()
        self._preempt()
        if now - self._last_sched >= self.cfg.schedule_every_s:
            created = self.q.ensure_scheduled(self.types, self.cfg.machine, self.cfg.machines_by_role, now)
            if created:
                self.log(f"scheduled {len(created)} job(s): {created}")
            self._last_sched = now
        self._claim_work()
        self._publish(now)

    def _reap_expired(self) -> None:
        for row in self.q.reap_expired():
            jid = row["id"]
            if jid in self.running:  # our own lease lapsed (a tick took too long): stop it, the queue owns it again
                self.log(f"lease lost for job {jid}; stopping it")
                self.running.pop(jid).handle.terminate(KILL_GRACE_S)
            elif pid_is_ours(row["runner_pid"], row["runner_start"], jid) and (row["leased_by"] or "").startswith(
                    f"{self.cfg.machine}:{self.cfg.hostname}:"):
                self.log(f"reap: stopping orphaned runner pid {row['runner_pid']} of job {jid}")
                kill_group(row["runner_pid"])

    def _finalize_finished(self) -> None:
        for jid, run in list(self.running.items()):
            rc = run.handle.poll()
            if rc is None:
                continue
            del self.running[jid]
            state = self.q.finish(jid, self.worker_id, rc, run.spec)
            self.log(f"job {jid} {run.spec.name} exit {rc} -> {state}")

    def _heartbeat(self) -> None:
        for jid, run in list(self.running.items()):
            if not self.q.heartbeat(jid, self.worker_id, self.cfg.lease_ttl):
                self.log(f"job {jid}: lease no longer ours, stopping")
                run.handle.terminate(KILL_GRACE_S)
                del self.running[jid]

    def _stop_and_release(self, row: Mapping[str, Any], reason: str, delay: int) -> None:
        jid = row["id"]
        run = self.running.pop(jid, None)
        if run is None:
            return
        self.log(f"stopping job {jid} ({run.spec.name}): {reason}")
        run.handle.terminate(KILL_GRACE_S)
        self.q.release(jid, self.worker_id, reason, delay_s=delay)

    def _memory_pressure(self) -> None:
        floor = self.cfg.reserve_mem_gb * PRESSURE_FRACTION
        if self.mem_avail() >= floor:
            self._pressure = 0
            return
        self._pressure += 1
        if self._pressure < PRESSURE_TICKS:
            return
        mine = [dict(r) for r in self.q.db.execute("SELECT * FROM jobs WHERE state IN ('leased','running')") if r["id"] in self.running]
        victims = [r for r in mine if self.types[r["type"]].preemptible]
        if victims:
            v = min(victims, key=lambda r: (r["priority"], -r["id"]))
            self._stop_and_release(v, f"memory pressure ({self.mem_avail():.1f} GB free, reserve {self.cfg.reserve_mem_gb:g}); will resume later", 300)
        elif mine:
            self.log(f"memory pressure but no preemptible job is running; leaving {[r['type'] for r in mine]} alone")
        self._pressure = 0

    def _preempt(self) -> None:
        victim = self.q.preemption_victim(self.cfg.machine, self.types, self.cfg.caps)
        if victim and victim["id"] in self.running:
            self._stop_and_release(victim, "preempted by a higher-priority job", 60)

    def _claim_work(self) -> None:
        skip: set[str] = set()
        self.blocked = ""
        if self.q.paused():
            self.blocked = "paused"
            return
        avail = self.mem_avail()
        if avail < self.cfg.reserve_mem_gb + 1.0:
            self.blocked = f"memory ({avail:.1f} GB free, reserve {self.cfg.reserve_mem_gb:g})"
            return
        for _ in range(8):  # at most a handful of claims per tick
            job = self.q.claim(self.worker_id, self.cfg.machine, self.types, self.cfg.caps, self.cfg.lease_ttl, skip)
            if job is None:
                return
            spec = self.types[job["type"]]
            needs_cuda = spec.needs_cuda or (spec.resource == "gpu" and self.cfg.cuda_required)
            if needs_cuda:
                ok, detail = self._cuda_ok()
                if not ok:
                    self.blocked = f"cuda: {detail}"
                    self.log(f"not starting {spec.name}: CUDA policy check failed: {detail}")
                    self.q.release(job["id"], self.worker_id, f"cuda blocked: {detail}", delay_s=300)
                    skip.add("gpu")
                    continue
            if spec.resource == "gpu" and not self.lock_free():
                self.blocked = "gpu lock held by another job (not started by this worker)"
                self.q.release(job["id"], self.worker_id, "GPU lock is held by something else", delay_s=120)
                skip.add("gpu")
                continue
            self._start(job, spec)

    def _extra(self) -> dict[str, str]:
        return {"python": self.cfg.python, "state": self.cfg.state_dir or f"{self.cfg.home}/.gs-queue"}

    def _argv(self, job: Mapping[str, Any], spec: JobType) -> list[str]:
        payload = json.loads(job["payload"] or "{}")
        day = day_stamp(self.now(), spec.tz)
        cmd = render_cmd(spec, payload, self.cfg.machine, self.cfg.repo, self.cfg.home, day, extra=self._extra())
        argv = [f"{self.cfg.repo}/scripts/gs_run.sh", "--name", f"gsq-{job['id']}-{spec.name}"]
        if spec.resource == "gpu":
            argv += ["--gpu", "--gpu-lock-timeout", "0"]
        if spec.timeout_s:
            argv += ["--timeout", str(spec.timeout_s)]
        if spec.min_free_gb is not None:
            argv += ["--min-free-gb", f"{spec.min_free_gb:g}"]
        return argv + list(spec.gs_args) + ["--"] + cmd

    def _start(self, job: dict[str, Any], spec: JobType) -> None:
        try:
            argv = self._argv(job, spec)
        except ConfigError as exc:
            self.log(f"job {job['id']} {spec.name}: {exc}")
            self.q.finish(job["id"], self.worker_id, 78, spec, error=str(exc))
            return
        env = dict(os.environ)
        try:
            env.update(render_env(spec, json.loads(job["payload"] or "{}"), self.cfg.machine, self.cfg.repo, self.cfg.home,
                                  day_stamp(self.now(), spec.tz), extra=self._extra()))
        except ConfigError as exc:
            self.q.finish(job["id"], self.worker_id, 78, spec, error=str(exc))
            return
        bindir = str(Path(self.cfg.python).parent)
        if bindir not in env.get("PATH", "").split(":"):
            env["PATH"] = f"{bindir}:" + env.get("PATH", "")  # jobs find the venv uvicorn/pip, even from a worktree
        env["PYTHONPATH"] = f"{self.cfg.repo}/packages/shared/src:" + env.get("PYTHONPATH", "")
        env["GS_JOB_ID"] = str(job["id"])
        env["GS_JOB_TYPE"] = spec.name
        env["GS_QUEUE_MACHINE"] = self.cfg.machine
        env["GS_STATE_DIR"] = self.cfg.state_dir or f"{self.cfg.home}/.gs-queue"
        if self.cfg.cuda_required:
            env["AOEP_REQUIRE_CUDA"] = "1"
        log_path = f"{self.cfg.logs_dir}/{job['id']}-{spec.name}.log"
        try:
            handle = self.runner.start(argv, env, self.cfg.repo, log_path)
        except OSError as exc:
            self.log(f"job {job['id']} {spec.name}: cannot start: {exc}")
            self.q.finish(job["id"], self.worker_id, 127, spec, error=f"cannot start: {exc}")
            return
        self.q.mark_running(job["id"], self.worker_id, handle.pid, handle.start_token)
        self.running[job["id"]] = Running(job, spec, handle, self.now())
        self.log(f"started job {job['id']} {spec.name} (pid {handle.pid}, resource {spec.resource}, attempt {job['attempts']})")

    def _publish(self, now: float) -> None:
        state = "paused" if self.q.paused() else ("busy" if self.running else "idle")
        if self.blocked.startswith("cuda"):
            state = "cuda-blocked"
        if self.running:
            self.q.set_setting("last_busy", now)
        self.q.set_setting("worker_state", {
            "pid": os.getpid(), "id": self.worker_id, "heartbeat": now, "state": state, "blocked": self.blocked,
            "running": sorted(self.running), "machine": self.cfg.machine,
        })

    # -- main loop ----------------------------------------------------------------------------
    def run_forever(self, tick_s: float, should_stop: Callable[[], bool]) -> None:
        n = self.recover()
        if n:
            self.log(f"recovered {n} job(s) from a previous worker")
        self.notify("READY=1")
        while not should_stop():
            try:
                self.tick()
            except Exception as exc:  # a bug in one tick must not kill the worker or orphan jobs
                self.log(f"tick error: {type(exc).__name__}: {exc}")
            time.sleep(tick_s)
        self.shutdown()
