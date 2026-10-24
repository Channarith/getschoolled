"""scripts/gs_run.sh and scripts/fleet_reap.sh on this machine (process-group mode; no systemd needed)."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
GS_RUN = REPO / "scripts" / "gs_run.sh"
REAP = REPO / "scripts" / "fleet_reap.sh"

pytestmark = pytest.mark.skipif(os.name != "posix", reason="bash job control needed")


@pytest.fixture
def env(tmp_path):
    """A fake `tmux` first on PATH reports the panes listed in $FAKE_TMUX_PANES, so tests never depend on
    (or touch) whatever tmux sessions the machine running them has."""
    fake = tmp_path / "fakebin"
    fake.mkdir()
    shim = fake / "tmux"
    shim.write_text('#!/bin/bash\n[ "$1" = "-S" ] && shift 2\n[ "$1" = "list-panes" ] && [ -f "$FAKE_TMUX_PANES" ] && cat "$FAKE_TMUX_PANES"\nexit 0\n')
    shim.chmod(0o755)
    e = dict(os.environ)
    e.update(GS_JOBS_DIR=str(tmp_path / "jobs"), GS_GPU_LOCK=str(tmp_path / "gpu.lock"), GS_MACHINE="default",
             FAKE_TMUX_PANES=str(tmp_path / "panes"))
    e["PATH"] = f"{fake}:{os.environ['PATH']}"
    return e


def sleeper(cwd, seconds=120):
    """A process that is not in a git repo and not in tmux: a plain stranger."""
    return subprocess.Popen(["sleep", str(seconds)], cwd=str(cwd))


def run(env, *args, timeout=60, **kw):
    return subprocess.run(["bash", str(GS_RUN), "--min-free-gb", "0", "--no-systemd", *args],
                          capture_output=True, text=True, env=env, timeout=timeout, **kw)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # a zombie still answers kill -0; treat it as dead only if its parent reaped it
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def records(env):
    return [json.loads(p.read_text()) for p in sorted(Path(env["GS_JOBS_DIR"]).glob("*.json"))]


def test_dry_run_prints_the_plan_and_starts_nothing(env, tmp_path):
    r = subprocess.run(["bash", str(GS_RUN), "--dry-run", "--gpu", "--timeout", "60", "--name", "demo", "--", "echo", "hi"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0
    for key in ("mem_max_gb", "cpu_quota", "gpu_lock", "timeout:", "command:"):
        assert key in r.stdout
    assert not (tmp_path / "jobs").exists() and not (tmp_path / "gpu.lock.owner").exists()


def test_usage_errors():
    assert subprocess.run(["bash", str(GS_RUN)], capture_output=True).returncode == 64
    assert subprocess.run(["bash", str(GS_RUN), "--bogus", "--", "true"], capture_output=True).returncode == 64


def test_exit_code_and_record(env):
    r = run(env, "--name", "demo", "--", "bash", "-c", "exit 3")
    assert r.returncode == 3
    (rec,) = records(env)
    assert rec["state"] == "failed" and rec["exit_code"] == 3 and rec["name"] == "demo"
    assert rec["limits"]["nice"] == 10 and rec["ended"] >= rec["started"]
    ok = run(env, "--", "true")
    assert ok.returncode == 0
    assert sorted(r["state"] for r in records(env)) == ["failed", "finished"]


def test_refuses_to_start_below_the_memory_floor(env):
    r = subprocess.run(["bash", str(GS_RUN), "--min-free-gb", "100000", "--", "true"], capture_output=True, text=True, env=env)
    assert r.returncode == 75 and "Not starting" in r.stderr
    assert not Path(env["GS_JOBS_DIR"]).exists()


def test_timeout_kills_the_whole_tree(env, tmp_path):
    pidfile = tmp_path / "grandchildren"
    script = f"sleep 300 & echo $! >> {pidfile}; sleep 301 & echo $! >> {pidfile}; wait"
    r = run(env, "--timeout", "3", "--name", "tmo", "--", "bash", "-c", script, timeout=60)
    assert r.returncode == 124
    time.sleep(0.5)
    pids = [int(x) for x in pidfile.read_text().split()]
    assert len(pids) == 2 and not any(alive(p) for p in pids)
    assert records(env)[0]["state"] == "timeout"


def test_sigterm_to_the_wrapper_leaves_no_children(env, tmp_path):
    pidfile = tmp_path / "pids"
    proc = subprocess.Popen(
        ["bash", str(GS_RUN), "--min-free-gb", "0", "--no-systemd", "--name", "sig", "--", "bash", "-c",
         f"sleep 300 & echo $! > {pidfile}; wait"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        time.sleep(0.1)
    child = int(pidfile.read_text().strip())
    assert alive(child)
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=40)
    time.sleep(0.5)
    assert not alive(child)
    assert records(env)[0]["state"] == "killed"


def test_second_gpu_job_cannot_start_while_the_first_holds_the_lock(env, tmp_path):
    started = tmp_path / "started"
    first = subprocess.Popen(
        ["bash", str(GS_RUN), "--min-free-gb", "0", "--no-systemd", "--gpu", "--name", "first", "--", "bash", "-c",
         f"touch {started}; sleep 20"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(60):
            if started.exists():
                break
            time.sleep(0.1)
        assert started.exists()
        owner = Path(env["GS_GPU_LOCK"] + ".owner").read_text()
        assert " first " in owner
        second = run(env, "--gpu", "--gpu-lock-timeout", "0", "--name", "second", "--", "true")
        assert second.returncode == 75 and "GPU lock" in second.stderr
    finally:
        first.send_signal(signal.SIGTERM)
        first.wait(timeout=40)
    assert not Path(env["GS_GPU_LOCK"] + ".owner").exists()
    third = run(env, "--gpu", "--gpu-lock-timeout", "0", "--name", "third", "--", "true")
    assert third.returncode == 0


def test_gpu_jobs_see_the_lock_as_already_held(env):
    """training/spark_nightly.sh re-locks unless GS_GPU_LOCK_HELD is set; gs_run --gpu must set it."""
    r = run(env, "--gpu", "--gpu-lock-timeout", "0", "--", "bash", "-c", "echo held=$GS_GPU_LOCK_HELD")
    assert "held=1" in r.stdout
    plain = run(env, "--", "bash", "-c", "echo held=${GS_GPU_LOCK_HELD:-none}")
    assert "held=none" in plain.stdout


def test_job_children_do_not_inherit_the_lock(env, tmp_path):
    """A daemonized child must not keep the GPU lock after the job ends."""
    r = run(env, "--gpu", "--gpu-lock-timeout", "0", "--name", "leaky", "--", "bash", "-c", "(sleep 5 &) ; exit 0")
    assert r.returncode == 0
    again = run(env, "--gpu", "--gpu-lock-timeout", "0", "--", "true")
    assert again.returncode == 0


def test_reap_is_dry_run_by_default_and_ignores_strangers(env, tmp_path):
    stranger = sleeper(tmp_path)
    try:
        r = subprocess.run(["bash", str(REAP)], capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 0 and "dry run" in r.stdout.lower()
        assert alive(stranger.pid)
        explicit = subprocess.run(["bash", str(REAP), "--pid", str(stranger.pid)], capture_output=True, text=True, env=env, timeout=60)
        assert "would stop" in explicit.stdout and alive(stranger.pid)
        killed = subprocess.run(["bash", str(REAP), "--pid", str(stranger.pid), "--yes"], capture_output=True, text=True, env=env, timeout=60)
        assert killed.returncode == 0
        stranger.wait(timeout=30)
        assert stranger.returncode is not None
    finally:
        if stranger.poll() is None:
            stranger.kill()
            stranger.wait()


def reap(env, *args):
    return subprocess.run(["bash", str(REAP), *args], capture_output=True, text=True, env=env, timeout=60)


def make_worktree(tmp_path):
    """A real git repo plus a linked worktree, like the Spark's gs-wt/spark-eval-gates."""
    main = tmp_path / "main"
    main.mkdir()
    git = ["git", "-C", str(main), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    wt = tmp_path / "gs-wt" / "spark-eval-gates"
    subprocess.run([*git, "worktree", "add", "-q", "-b", "feat/eval", str(wt)], check=True)
    return main, wt


def test_reap_refuses_a_process_running_in_a_git_worktree(env, tmp_path):
    main, wt = make_worktree(tmp_path)
    proc = sleeper(wt)
    try:
        dry = reap(env, "--pid", str(proc.pid))
        assert "REFUSING" in dry.stdout and "worktree spark-eval-gates" in dry.stdout and "--i-know-owner" in dry.stdout
        no_flag = reap(env, "--pid", str(proc.pid), "--yes")
        assert "REFUSING" in no_flag.stdout and alive(proc.pid)
        # the flag alone, with no explicit pid, never opens the door
        assert "does nothing without an explicit --pid" in reap(env, "--i-know-owner", "--yes").stdout
        assert alive(proc.pid)
        # a plain checkout (not a linked worktree) is not treated as owned
        plain = sleeper(main)
        try:
            assert "would stop pid" in reap(env, "--pid", str(plain.pid)).stdout
        finally:
            plain.kill()
            plain.wait()
        forced = reap(env, "--pid", str(proc.pid), "--i-know-owner", "--yes")
        assert "stopping pid" in forced.stdout and "worktree spark-eval-gates" in forced.stdout
        proc.wait(timeout=30)
        assert proc.returncode is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_reap_refuses_a_process_under_a_tmux_pane_shell(env, tmp_path):
    shell = subprocess.Popen(["bash", "-c", "sleep 120; true"], cwd=str(tmp_path))  # bash stays the parent
    try:
        child = None
        for _ in range(50):
            out = subprocess.run(["pgrep", "-P", str(shell.pid)], capture_output=True, text=True).stdout.split()
            if out:
                child = int(out[0])
                break
            time.sleep(0.1)
        assert child is not None
        Path(env["FAKE_TMUX_PANES"]).write_text(f"{shell.pid} nllb-speech main\n999999 other main\n")
        dry = reap(env, "--pid", str(child))
        assert "REFUSING" in dry.stdout and "tmux session 'nllb-speech'" in dry.stdout
        assert "REFUSING" in reap(env, "--pid", str(child), "--yes").stdout and alive(child)
        # naming the shell itself (the pane) is just as protected
        assert "REFUSING" in reap(env, "--pid", str(shell.pid), "--yes").stdout and alive(shell.pid)
        done = reap(env, "--pid", str(child), "--i-know-owner", "--yes")
        assert "stopping pid" in done.stdout
        for _ in range(100):
            if not alive(child):
                break
            time.sleep(0.1)
        assert not alive(child)
    finally:
        shell.kill()
        shell.wait()


def test_reap_never_signals_the_parent_of_a_zombie_owned_by_a_tmux_session(env, tmp_path):
    """--zombie-parents does not override the owner check: only --pid with --i-know-owner can."""
    parent = subprocess.Popen(["bash", "-c", "sleep 0.2 & exec sleep 120"], cwd=str(tmp_path))
    try:
        time.sleep(1.0)  # the background sleep exits and stays a zombie: bash was replaced by sleep, which never waits
        zombies = subprocess.run(["ps", "-axo", "pid=,ppid=,stat="], capture_output=True, text=True).stdout.splitlines()
        mine = [ln.split()[0] for ln in zombies if ln.split()[1:2] == [str(parent.pid)] and ln.split()[2].startswith("Z")]
        if not mine:
            pytest.skip("no zombie produced on this platform")
        Path(env["FAKE_TMUX_PANES"]).write_text(f"{parent.pid} course-translate main\n")
        r = reap(env, "--zombie-parents", "--yes")
        assert f"zombie {mine[0]}" in r.stdout and "REFUSING" in r.stdout
        assert alive(parent.pid)
    finally:
        parent.kill()
        parent.wait()


def test_gs_run_jobs_inside_a_worktree_are_not_protected(env, tmp_path):
    """A job started through gs_run is ours even if it runs in a worktree or tmux: the reaper may stop it."""
    main, wt = make_worktree(tmp_path)
    proc = subprocess.Popen(
        ["bash", str(GS_RUN), "--min-free-gb", "0", "--no-systemd", "--name", "mine", "--", "sleep", "120"],
        env=env, cwd=str(wt), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        for _ in range(80):
            recs = records(env) if Path(env["GS_JOBS_DIR"]).exists() else []
            if recs and recs[0].get("child_pid"):
                break
            time.sleep(0.1)
        child = records(env)[0]["child_pid"]
        out = reap(env, "--pid", str(child))
        assert "REFUSING" not in out.stdout and "started via gs_run" in out.stdout
    finally:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=40)


def test_reap_marks_dead_job_records_finished(env, tmp_path):
    jobs = Path(env["GS_JOBS_DIR"])
    jobs.mkdir(parents=True)
    rec = jobs / "old.json"
    rec.write_text(json.dumps({"id": "old", "name": "ghost", "state": "running", "pid": 999999, "child_pid": None,
                               "started": 1, "ended": None, "exit_code": None, "cmd": "x"}))
    dry = subprocess.run(["bash", str(REAP)], capture_output=True, text=True, env=env, timeout=60)
    assert "ghost" in dry.stdout and json.loads(rec.read_text())["state"] == "running"
    subprocess.run(["bash", str(REAP), "--yes"], capture_output=True, text=True, env=env, timeout=60)
    assert json.loads(rec.read_text())["state"] == "lost"


def test_install_units_fills_every_placeholder(tmp_path, env):
    dest = tmp_path / "units"
    r = subprocess.run(["bash", str(REPO / "scripts" / "fleet" / "install-units.sh"), "--dest", str(dest)],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    slice_text = (dest / "gs-batch.slice").read_text()
    assert "@" not in slice_text.replace("@", "", 0) or "@MEM" not in slice_text
    assert "MemoryMax=" in slice_text and "CPUQuota=" in slice_text and "%" in slice_text
    service = (dest / "gs-job@.service").read_text()
    assert str(REPO) in service and "Slice=gs-batch.slice" in service
    assert "RestartPreventExitStatus=75 64" in service and "StartLimitBurst=3" in service
    assert "KillMode=control-group" in service
    assert "@REPO@" not in (dest / "gs-fleet-check.service").read_text()


def test_scripts_have_valid_bash_syntax():
    for name in ("gs_run.sh", "fleet_status.sh", "fleet_reap.sh", "fleet/probe.sh", "fleet/install-units.sh"):
        path = REPO / "scripts" / name
        assert path.exists(), name
        assert subprocess.run(["bash", "-n", str(path)], capture_output=True).returncode == 0, name


FLOCK_SHIM = """#!/usr/bin/env python3
import fcntl, sys
a = sys.argv[1:]
assert a[0] == "-n", "shim supports flock -n FD only"
try:
    fcntl.flock(int(a[1]), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(1)
"""


@pytest.fixture(params=["lockdir", "flock"])
def lenv(request, env, tmp_path):
    """Same jobs, once with the portable lock-directory path and once with util-linux flock semantics (a shim: the
    lock lives on the open file description bash keeps as fd 9/8, exactly like the real tool)."""
    if request.param == "flock":
        shim = tmp_path / "fakebin" / "flock"
        shim.write_text(FLOCK_SHIM)
        shim.chmod(0o755)
    return env


def start(env, *args, **kw):
    return subprocess.Popen(["bash", str(GS_RUN), "--min-free-gb", "0", "--no-systemd", *args], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, start_new_session=True, **kw)


def stop(proc):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            proc.kill()


def wait_for(path, tries=100):
    for _ in range(tries):
        if Path(path).exists():
            return True
        time.sleep(0.1)
    return False


def test_a_second_copy_of_the_same_name_is_refused_at_once(lenv, tmp_path):
    started = tmp_path / "started"
    first = start(lenv, "--gpu", "--name", "voice-clone-x", "--", "bash", "-c", f"touch {started}; sleep 30")
    try:
        assert wait_for(started)
        second = run(lenv, "--gpu", "--name", "voice-clone-x", "--", "true", timeout=20)
        assert second.returncode == 75 and "already queued or running" in second.stderr
        other = run(lenv, "--name", "something-else", "--", "true")
        assert other.returncode == 0
    finally:
        stop(first)
    assert run(lenv, "--name", "voice-clone-x", "--", "true").returncode == 0


def test_a_queued_job_dies_promptly_on_sigterm(lenv, tmp_path):
    started = tmp_path / "started"
    holder = start(lenv, "--gpu", "--name", "holder", "--", "bash", "-c", f"touch {started}; sleep 60")
    try:
        assert wait_for(started)
        waiter = start(lenv, "--gpu", "--name", "waiter", "--", "true")
        time.sleep(1.5)
        assert waiter.poll() is None
        t0 = time.time()
        waiter.send_signal(signal.SIGTERM)
        waiter.wait(timeout=15)
        assert time.time() - t0 < 10
    finally:
        stop(holder)


def test_idle_watchdog_kills_a_hung_background_job_and_frees_the_lock(env, tmp_path):
    env = dict(env, GS_IDLE_POLL_S="1", GS_GPU_UTIL_CMD="echo 0")
    r = run(env, "--gpu", "--priority", "background", "--idle-timeout", "3", "--name", "hung", "--", "bash", "-c", "sleep 300",
            timeout=60)
    assert r.returncode == 125 and "no CPU progress" in r.stderr
    assert records(env)[0]["state"] == "idle-killed" and records(env)[0]["priority"] == "background"
    assert run(env, "--gpu", "--gpu-lock-timeout", "0", "--name", "next", "--", "true").returncode == 0


def test_idle_watchdog_spares_a_job_the_gpu_is_busy_with(env):
    env = dict(env, GS_IDLE_POLL_S="1", GS_GPU_UTIL_CMD="echo 87")
    r = run(env, "--priority", "background", "--idle-timeout", "2", "--name", "busy", "--", "bash", "-c", "sleep 5", timeout=60)
    assert r.returncode == 0


def test_interactive_job_preempts_a_background_holder_after_the_wait(lenv, tmp_path):
    lenv = dict(lenv, GS_POLL_S="1", GS_PREEMPT_GRACE_S="2", GS_IDLE_POLL_S="100")
    started = tmp_path / "started"
    holder = start(lenv, "--gpu", "--priority", "background", "--idle-timeout", "0", "--name", "nightly", "--", "bash", "-c",
                   f"touch {started}; sleep 300")
    try:
        assert wait_for(started)
        r = run(lenv, "--gpu", "--priority", "interactive", "--preempt-after", "2", "--name", "voice-clone", "--", "true", timeout=60)
        assert r.returncode == 0 and "stopping background holder 'nightly'" in r.stderr
        holder.wait(timeout=30)
    finally:
        stop(holder)


def test_interactive_job_never_preempts_another_interactive_holder(lenv, tmp_path):
    lenv = dict(lenv, GS_POLL_S="1")
    started = tmp_path / "started"
    holder = start(lenv, "--gpu", "--name", "demo", "--", "bash", "-c", f"touch {started}; sleep 30")
    try:
        assert wait_for(started)
        r = run(lenv, "--gpu", "--gpu-lock-timeout", "5", "--preempt-after", "1", "--name", "clone", "--", "true", timeout=60)
        assert r.returncode == 75 and holder.poll() is None
    finally:
        stop(holder)


def test_priority_must_be_known(env):
    assert run(env, "--priority", "urgent", "--", "true").returncode == 64


GATE = REPO / "scripts" / "fleet" / "spark_gate.sh"


def gate(env, **extra):
    return subprocess.run(["bash", str(GATE)], capture_output=True, text=True, env=dict(env, **extra), timeout=30)


def test_gate_lines_name_the_lock_holder_the_waiters_and_the_memory_verdict(lenv, tmp_path):
    started = tmp_path / "started"
    idle = gate(lenv, GS_GATE_FAKE_AVAIL_GB="40")
    assert idle.returncode == 0
    assert "GPU lock : free" in idle.stdout and "Queue    : nothing waiting" in idle.stdout
    assert "40 GB available, gate 16 GB: OK" in idle.stdout
    holder = start(lenv, "--gpu", "--priority", "background", "--idle-timeout", "0", "--name", "nightly", "--", "bash", "-c",
                   f"touch {started}; sleep 60")
    waiters = []
    try:
        assert wait_for(started)
        waiters = [start(lenv, "--gpu", "--name", n, "--", "true") for n in ("voice-clone-voxcpm2", "voice-clone-cosyvoice2")]
        time.sleep(2.5)
        busy = gate(lenv, GS_GATE_FAKE_AVAIL_GB="9")
        assert "held by 'nightly'" in busy.stdout and "background" in busy.stdout
        assert "BLOCKED" in busy.stdout
        assert "2 waiting" in busy.stdout and "voice-clone-voxcpm2" in busy.stdout and "voice-clone-cosyvoice2" in busy.stdout
        assert "nightly" not in busy.stdout.split("Queue")[1]          # the holder (and its subshells) are not waiters
    finally:
        for w in waiters:
            stop(w)
        stop(holder)


def test_gate_reports_a_lab_port_that_is_down():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    up = s.getsockname()[1]
    try:
        r = subprocess.run(["bash", str(GATE)], capture_output=True, text=True, timeout=30,
                           env={**os.environ, "GS_ENROLL_PORT": str(up), "GS_LAB_PORT": "1", "GS_GATE_FAKE_AVAIL_GB": "40"})
    finally:
        s.close()
    assert f"enrollment :{up} listening" in r.stdout and "listening lab :1 DOWN" in r.stdout


def test_fleet_status_runs_with_a_python_that_has_the_dependencies(tmp_path):
    hosts = tmp_path / "hosts.conf"
    hosts.write_text("mac - local\n")
    env = dict(os.environ, FLEET_HOSTS_FILE=str(hosts), FLEET_SAMPLE_SECONDS="0", FLEET_PYTHON=sys.executable,
               GS_JOBS_DIR=str(tmp_path / "jobs"))
    r = subprocess.run(["bash", str(REPO / "scripts" / "fleet_status.sh"), "--local", "--no-gate"], capture_output=True, text=True,
                       env=env, cwd=str(REPO), timeout=120)
    assert "ModuleNotFoundError" not in r.stderr and r.stdout.splitlines()[0].startswith("HOST"), r.stdout + r.stderr
