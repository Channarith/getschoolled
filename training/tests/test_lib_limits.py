"""gs_stage: exit codes, timeout, low-memory abort, and no orphaned processes."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parents[1] / "lib_limits.sh"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


def run(snippet: str, **env) -> subprocess.CompletedProcess:
    full_env = {**os.environ, "GS_TIMEOUT_SCALE": "1", "GS_KILL_AFTER": "2", "GS_MEM_CHECK_EVERY": "1",
                "GS_PROFILE": "generic", "GS_RUN": "/nonexistent", **env}
    return subprocess.run([BASH, "-c", f". {LIB}\n{snippet}"], capture_output=True, text=True,
                          env=full_env, timeout=60)


def alive(marker: str) -> bool:
    return subprocess.run(["pgrep", "-f", marker], capture_output=True).returncode == 0


def test_returns_the_commands_exit_code():
    assert run('gs_stage ok 1 true; echo "rc=$?"').stdout.strip().endswith("rc=0")
    out = run('gs_stage bad 1 bash -c "exit 7"; echo "rc=$?"')
    assert "rc=7" in out.stdout


def test_timeout_kills_the_whole_process_tree():
    marker = "sleep 7771"
    out = run(f'gs_stage slow 2 bash -c "{marker} & {marker}; wait"; echo "rc=$?"')
    assert "rc=124" in out.stdout, out.stdout + out.stderr
    time.sleep(0.5)
    assert not alive(marker), "timed-out stage left child processes running"


def test_low_free_memory_aborts_the_stage_and_cleans_up():
    marker = "sleep 7772"
    out = run(f'gs_stage hog 30 bash -c "{marker} & {marker}; wait"; echo "rc=$?"', GS_FAKE_AVAIL_GB="1")
    assert "rc=75" in out.stdout, out.stdout + out.stderr
    assert "ABORT" in out.stderr
    time.sleep(0.5)
    assert not alive(marker)


def test_preflight_refuses_when_memory_is_short():
    out = run('gs_preflight 10; echo "rc=$?"', GS_FAKE_AVAIL_GB="5")
    assert "rc=75" in out.stdout and "REFUSING TO START" in out.stderr
    assert "rc=0" in run('gs_preflight 1; echo "rc=$?"', GS_FAKE_AVAIL_GB="50").stdout


def test_no_zombie_left_behind():
    out = run('gs_stage quick 1 true; sleep 0.2; ps -o stat= --ppid $$ | grep -c Z || true')
    assert out.stdout.strip().splitlines()[-1] == "0"


def test_profile_budgets():
    out = run('gs_init; echo "$GS_PROFILE $GS_RESERVE_GB $GS_RESERVE_CORES $GS_ABORT_FREE_GB"', GS_PROFILE="spark")
    assert out.stdout.split() == ["spark", "16", "2", "6"]
    out = run('gs_init; echo "$GS_PROFILE $GS_RESERVE_GB $GS_RESERVE_CORES $GS_ABORT_FREE_GB"', GS_PROFILE="ibuypower")
    assert out.stdout.split() == ["ibuypower", "6", "2", "3"]


def test_uses_gs_run_when_present_with_its_real_options(tmp_path):
    fake = tmp_path / "gs_run.sh"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = --help ]; then echo 'options: --timeout SEC --mem-max GB'; exit 0; fi\n"
        "echo \"ARGS: $*\" > \"$GS_RUN_LOG\"\n"
        "while [ \"$1\" != -- ]; do shift; done; shift; exec \"$@\"\n", encoding="utf-8")
    fake.chmod(0o755)
    log = tmp_path / "args.log"
    out = run('gs_stage fleet 5 bash -c "exit 4"; echo "rc=$?"', GS_RUN=str(fake), GS_RUN_LOG=str(log), GS_FAKE_TOTAL_GB="64")
    assert "rc=4" in out.stdout and "mode=gs_run.sh" in out.stdout, out.stdout + out.stderr
    args = log.read_text(encoding="utf-8")
    assert "--name fleet" in args and "--timeout 5" in args and "--mem-max 60" in args and "--cpus" in args
    assert "--gpu" not in args  # the nightly already holds the GPU lock


def test_unknown_total_ram_means_no_ceiling_not_a_negative_one():
    out = run('gs_init; echo "[$GS_MEM_MAX_GB]"', GS_PROFILE="generic", PATH="/usr/bin:/bin")
    value = out.stdout.strip().strip("[]")
    assert value == "" or int(value) > 0
