"""Worker behaviour with fake processes, plus a few real child processes for crash recovery and zombies."""
from __future__ import annotations

import fcntl
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aoep_shared.fleet_queue import JobType, Queue
from aoep_shared.fleet_worker import (
    SubprocessRunner,
    Worker,
    WorkerConfig,
    gpu_lock_free,
    kill_group,
    pid_is_ours,
    process_start_token,
    sd_notify,
)

CAPS = {"gpu": 1, "cpu": 2, "net": 2}


class Clock:
    def __init__(self, t: float = 5_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


def spec(name: str, **kw) -> JobType:
    return JobType.from_dict({"name": name, "cmd": ["{python}", "-c", "print(1)"], "resource": "cpu", **kw})


class FakeHandle:
    _next = 4000

    def __init__(self):
        FakeHandle._next += 1
        self.pid = FakeHandle._next
        self.start_token = f"tok{self.pid}"
        self.rc: int | None = None
        self.terminated = False

    def poll(self):
        return self.rc

    def terminate(self, grace_s: float = 30) -> int:
        self.terminated = True
        self.rc = -15
        return -15


class FakeRunner:
    def __init__(self):
        self.started: list[tuple[list[str], dict, FakeHandle]] = []

    def start(self, argv, env, cwd, log_path):
        h = FakeHandle()
        self.started.append((argv, dict(env), h))
        return h

    def handle_for(self, type_name: str) -> FakeHandle:
        return next(h for a, e, h in reversed(self.started) if e.get("GS_JOB_TYPE") == type_name)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def q(clock: Clock) -> Queue:
    return Queue(":memory:", clock=clock)


def make(q: Queue, types: dict[str, JobType], clock: Clock, tmp_path: Path, *, machine="spark", mem=lambda: 64.0,
         cuda=lambda: (True, "ok torch"), lock_free=lambda: True, runner=None, cuda_required=True, reserve=16.0):
    cfg = WorkerConfig(machine=machine, repo="/repo", home="/home/u", python="/venv/bin/python", caps=CAPS,
                       reserve_mem_gb=reserve, cuda_required=cuda_required, logs_dir=str(tmp_path / "logs"), hostname="host")
    runner = runner or FakeRunner()
    logs: list[str] = []
    w = Worker(q, types, cfg, runner, now=clock, mem_avail=mem, cuda_check=cuda, lock_free=lock_free,
               notify=lambda m: None, log=logs.append)
    w.logs = logs  # type: ignore[attr-defined]
    return w, runner


# ---- starting jobs ------------------------------------------------------------------------------
def test_job_is_started_through_gs_run_with_limits_and_cuda_env(q, clock, tmp_path):
    s = spec("train", resource="gpu", needs_cuda=True, timeout_s=3600, min_free_gb=8)
    q.enqueue(s)
    w, runner = make(q, {"train": s}, clock, tmp_path)
    w.tick()
    argv, env, _ = runner.started[0]
    assert argv[0] == "/repo/scripts/gs_run.sh"
    assert "--gpu" in argv and argv[argv.index("--gpu-lock-timeout") + 1] == "0", "never block waiting for the GPU lock"
    assert argv[argv.index("--timeout") + 1] == "3600" and argv[argv.index("--min-free-gb") + 1] == "8"
    assert argv[argv.index("--name") + 1].startswith("gsq-") and argv[argv.index("--") + 1:] == ["/venv/bin/python", "-c", "print(1)"]
    assert env["AOEP_REQUIRE_CUDA"] == "1" and env["GS_JOB_TYPE"] == "train"
    assert env["PYTHONPATH"].startswith("/repo/packages/shared/src")
    assert env["PATH"].startswith("/venv/bin:"), "jobs find the venv tools even when run from a worktree"
    assert q.get(1)["state"] == "running" and q.get(1)["runner_pid"] == runner.started[0][2].pid


def test_finish_and_failure_paths(q, clock, tmp_path):
    ok, bad = spec("fine", priority=60), spec("flaky", priority=50, max_attempts=2, backoff_s=60)
    types = {"fine": ok, "flaky": bad}
    q.enqueue(ok)
    q.enqueue(bad)
    w, runner = make(q, types, clock, tmp_path)
    w.tick()
    runner.handle_for("fine").rc = 0
    runner.handle_for("flaky").rc = 3
    w.tick()
    assert q.get(1)["state"] == "done"
    assert q.get(2)["state"] == "queued" and q.get(2)["not_before"] > clock.t and "retry" in q.get(2)["error"]
    assert not w.running


def test_never_two_gpu_jobs_on_one_machine(q, clock, tmp_path):
    a, b = spec("one", resource="gpu", needs_cuda=True), spec("two", resource="gpu", needs_cuda=True)
    q.enqueue(a)
    q.enqueue(b)
    w, runner = make(q, {"one": a, "two": b}, clock, tmp_path)
    for _ in range(3):
        w.tick()
    assert len(runner.started) == 1, "the second GPU job waits"
    assert sum(1 for r in q.db.execute("SELECT state FROM jobs") if r["state"] in ("leased", "running")) == 1


def test_missing_placeholder_value_kills_the_job_as_a_config_error(q, clock, tmp_path):
    s = spec("needs-arg", cmd=["echo", "{nothing_set}"])
    q.enqueue(s)
    w, runner = make(q, {"needs-arg": s}, clock, tmp_path)
    w.tick()
    assert not runner.started and q.get(1)["state"] == "dead" and "nothing_set" in q.get(1)["error"]


# ---- gates --------------------------------------------------------------------------------------
def test_gpu_job_does_not_start_when_cuda_check_fails_but_other_work_does(q, clock, tmp_path):
    gpu, cpu = spec("gpu-job", resource="gpu", needs_cuda=True, priority=90), spec("cpu-job", priority=10)
    q.enqueue(gpu)
    q.enqueue(cpu)
    w, runner = make(q, {"gpu-job": gpu, "cpu-job": cpu}, clock, tmp_path, cuda=lambda: (False, "torch.cuda.is_available() is False"))
    w.tick()
    types_started = [e["GS_JOB_TYPE"] for _, e, _ in runner.started]
    assert types_started == ["cpu-job"], "no silent CPU fallback for GPU work; other work continues"
    state = q.get_setting("worker_state")
    assert state["state"] == "cuda-blocked" and "cuda" in state["blocked"]
    assert q.get(1)["state"] == "queued" and q.get(1)["attempts"] == 1
    assert q.get(1)["not_before"] > clock.t, "retried later, not every tick"


def test_cuda_check_result_is_cached_so_a_broken_gpu_is_not_hammered(q, clock, tmp_path):
    calls = []
    gpu = spec("gpu-job", resource="gpu", needs_cuda=True)
    q.enqueue(gpu)
    w, _ = make(q, {"gpu-job": gpu}, clock, tmp_path, cuda=lambda: (calls.append(1) or (False, "broken")))
    for _ in range(4):
        w.tick()
        clock.advance(15)
    assert len(calls) == 1


def test_gpu_lock_held_by_someone_else_defers_the_job(q, clock, tmp_path):
    gpu = spec("gpu-job", resource="gpu", needs_cuda=True)
    q.enqueue(gpu)
    w, runner = make(q, {"gpu-job": gpu}, clock, tmp_path, lock_free=lambda: False)
    w.tick()
    assert not runner.started and "gpu lock" in q.get_setting("worker_state")["blocked"]
    assert q.get(1)["state"] == "queued"


def test_nothing_starts_below_the_memory_reserve_or_when_paused(q, clock, tmp_path):
    s = spec("job")
    q.enqueue(s)
    w, runner = make(q, {"job": s}, clock, tmp_path, mem=lambda: 10.0, reserve=16.0)
    w.tick()
    assert not runner.started and "memory" in q.get_setting("worker_state")["blocked"]
    w2, runner2 = make(q, {"job": s}, clock, tmp_path)
    q.set_setting("paused", True)
    w2.tick()
    assert not runner2.started and q.get_setting("worker_state")["state"] == "paused"


# ---- preemption and memory pressure ---------------------------------------------------------------
def test_high_priority_job_preempts_and_the_victim_resumes_later(q, clock, tmp_path):
    low = spec("low", resource="gpu", needs_cuda=True, priority=30, preemptible=True)
    high = spec("high", resource="gpu", needs_cuda=True, priority=90)
    types = {"low": low, "high": high}
    q.enqueue(low)
    w, runner = make(q, types, clock, tmp_path)
    w.tick()
    victim_handle = runner.handle_for("low")
    q.enqueue(high)
    w.tick()
    assert victim_handle.terminated, "the whole job tree is stopped (gs_run cleans up its children)"
    assert [e["GS_JOB_TYPE"] for _, e, _ in runner.started] == ["low", "high"], "the important job starts at once"
    assert q.get(1)["state"] == "queued" and q.get(1)["attempts"] == 1, "preemption does not cost an attempt"
    runner.handle_for("high").rc = 0
    w.tick()
    clock.advance(120)
    w.tick()
    assert [e["GS_JOB_TYPE"] for _, e, _ in runner.started][-1] == "low", "the preempted job resumes when the GPU is free"


def test_memory_pressure_stops_the_lowest_priority_preemptible_job_only(q, clock, tmp_path):
    keep = spec("train", resource="cpu", priority=90, preemptible=False)
    shed = spec("ingest", resource="cpu", priority=30, preemptible=True)
    types = {"train": keep, "ingest": shed}
    q.enqueue(keep)
    q.enqueue(shed)
    mem = {"v": 64.0}
    w, runner = make(q, types, clock, tmp_path, mem=lambda: mem["v"])
    w.tick()
    assert len(runner.started) == 2
    mem["v"] = 5.0  # reserve 16 -> floor 12
    w.tick()
    assert not runner.handle_for("ingest").terminated, "one low reading is not enough"
    w.tick()
    assert runner.handle_for("ingest").terminated and not runner.handle_for("train").terminated
    assert q.get(2)["state"] == "queued" and "memory pressure" in q.get(2)["error"]
    assert q.get(1)["state"] == "running"


def test_memory_pressure_never_touches_a_non_preemptible_job(q, clock, tmp_path):
    keep = spec("train", priority=90, preemptible=False)
    q.enqueue(keep)
    w, runner = make(q, {"train": keep}, clock, tmp_path, mem=lambda: 64.0)
    w.tick()
    w.mem_avail = lambda: 2.0
    w.tick()
    w.tick()
    assert not runner.handle_for("train").terminated
    assert any("no preemptible job" in m for m in w.logs)


# ---- leases ------------------------------------------------------------------------------------
def test_lost_lease_stops_the_job(q, clock, tmp_path):
    s = spec("job")
    q.enqueue(s)
    w, runner = make(q, {"job": s}, clock, tmp_path)
    w.tick()
    h = runner.handle_for("job")
    clock.advance(1000)  # a tick took far too long: lease lapsed and someone reaped it
    q.reap_expired()
    w.tick()
    assert h.terminated and not w.running


def test_shutdown_stops_children_and_returns_jobs(q, clock, tmp_path):
    s = spec("job")
    q.enqueue(s)
    w, runner = make(q, {"job": s}, clock, tmp_path)
    w.tick()
    w.shutdown()
    assert runner.handle_for("job").terminated and q.get(1)["state"] == "queued" and not w.running


# ---- real processes -----------------------------------------------------------------------------
def _sleeper(job_id: int, token_ok: bool = True) -> subprocess.Popen:
    """A real child that looks like a gs_run runner for the job (its argv contains gsq-<id>-)."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", f"gsq-{job_id}-test"],
                            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_recover_stops_only_the_leftover_runner_it_can_identify(q, clock, tmp_path):
    s = spec("job")
    types = {"job": s}
    for _ in range(3):
        q.enqueue(s)
    mine, decoy_pid_reuse, other_job = _sleeper(1), _sleeper(2), _sleeper(99)
    try:
        time.sleep(0.4)
        old_owner = "spark:host:99999"
        for jid, proc, tok in ((1, mine, process_start_token(mine.pid)), (2, decoy_pid_reuse, "WRONG-START-TIME"),
                               (3, other_job, process_start_token(other_job.pid))):
            q.db.execute("UPDATE jobs SET state='running', leased_by=?, lease_expires=?, runner_pid=?, runner_start=? WHERE id=?",
                         (old_owner, clock.t + 100, proc.pid, tok, jid))
        assert pid_is_ours(mine.pid, process_start_token(mine.pid), 1)
        assert not pid_is_ours(decoy_pid_reuse.pid, "WRONG-START-TIME", 2), "a reused pid (different start time) is not ours"
        assert not pid_is_ours(other_job.pid, process_start_token(other_job.pid), 3), "name does not match this job id"
        w, _ = make(q, types, clock, tmp_path)
        assert w.recover() == 3
        mine.wait(timeout=40)
        assert mine.returncode is not None, "the identified leftover runner was stopped"
        assert decoy_pid_reuse.poll() is None and other_job.poll() is None, "processes we cannot positively identify are never touched"
        assert all(q.get(i)["state"] == "queued" for i in (1, 2, 3))
    finally:
        for p in (mine, decoy_pid_reuse, other_job):
            if p.poll() is None:
                p.kill()
            p.wait()


def test_kill_group_takes_the_whole_tree_and_leaves_no_zombie(tmp_path):
    parent = subprocess.Popen(
        [sys.executable, "-c", "import subprocess,time,sys; subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)']); time.sleep(120)"],
        start_new_session=True)
    time.sleep(0.5)
    pgid = os.getpgid(parent.pid)
    kill_group(parent.pid, grace_s=5)
    parent.wait(timeout=10)
    time.sleep(0.3)
    with pytest.raises(ProcessLookupError):
        os.killpg(pgid, 0)  # nothing is left in the group, children included


def _fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    stub = repo / "scripts" / "gs_run.sh"
    stub.write_text('#!/usr/bin/env bash\nwhile [ "$1" != "--" ]; do shift; done; shift; exec "$@"\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return repo


def test_real_run_finishes_reaps_the_child_and_leaves_no_zombies(q, clock, tmp_path):
    repo = _fake_repo(tmp_path)
    s = JobType.from_dict({"name": "real", "cmd": ["{python}", "-c", "print('hello from a job')"], "resource": "cpu"})
    q.enqueue(s)
    cfg = WorkerConfig(machine="kalel", repo=str(repo), home=str(tmp_path), python=sys.executable, caps=CAPS,
                       reserve_mem_gb=1.0, cuda_required=False, logs_dir=str(tmp_path / "logs"), hostname="host")
    w = Worker(q, {"real": s}, cfg, SubprocessRunner(), now=time.time, mem_avail=lambda: 64.0, notify=lambda m: None, log=lambda m: None)
    q.clock = time.time
    w.tick()
    deadline = time.time() + 15
    while w.running and time.time() < deadline:
        time.sleep(0.2)
        w.tick()
    assert q.get(1)["state"] == "done" and q.get(1)["exit_code"] == 0
    assert "hello from a job" in (tmp_path / "logs" / "1-real.log").read_text()
    with pytest.raises(ChildProcessError):
        os.waitpid(-1, os.WNOHANG)  # no unreaped (zombie) children of this process remain


# ---- small helpers ------------------------------------------------------------------------------
def test_gpu_lock_free_reports_a_held_lock(tmp_path):
    lock = str(tmp_path / "gpu.lock")
    assert gpu_lock_free(lock)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert not gpu_lock_free(lock)
    finally:
        os.close(fd)
    assert gpu_lock_free(lock)


def test_sd_notify_is_a_no_op_outside_systemd(monkeypatch):
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    sd_notify("WATCHDOG=1")  # must not raise
