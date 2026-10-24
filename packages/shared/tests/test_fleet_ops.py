"""Operations layer around the queue: status findings, systemd units, installer, shard CLI, license guard."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from aoep_shared.fleet_status import CRIT, INFO, WARN, analyze, parse_report
from aoep_shared.fleet_worker import SubprocessRunner

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = REPO / "scripts"
UNITS = SCRIPTS / "fleet" / "systemd"
NOW = 2_000_000_000.0


# ---- queue findings in fleet_status -------------------------------------------------------------
def report(queue: str | dict, name: str = "spark") -> object:
    body = queue if isinstance(queue, str) else json.dumps(queue)
    text = f"FLEET_PROBE 1\nhost={name}\nos=Linux\nnow={int(NOW)}\ncpus=20\nload=0.5 0.5 0.5\nmem_total_kb=125000000\nmem_avail_kb=70000000\n[queue]\n{body}\n[end]\n"
    return parse_report(name, text)


def status(**over) -> dict:
    base = {"machine": "spark", "now": NOW, "counts": {"queued": 2}, "running": [], "queued_eligible": 0, "queued_blocked": {},
            "oldest_eligible_age_s": 0, "stale_leases": 0, "last_success": {}, "dead_24h": [], "paused": False, "disabled": [],
            "caps": {"gpu": 1}, "worker": {"state": "idle", "heartbeat": NOW - 20, "blocked": ""}, "last_busy": NOW - 60}
    base.update(over)
    return base


def codes(rep) -> dict[str, str]:
    return {f.code: f.severity for f in analyze(rep)}


def test_healthy_busy_machine_has_only_a_summary():
    rep = report(status(running=[{"id": 1, "type": "finetune-nightly"}], last_success={"frozen-eval": NOW - 7200}))
    found = codes(rep)
    assert found.get("QUEUE_SUMMARY") == INFO
    assert not {c for c in found if c.startswith(("WORKER", "QUEUE_STALE", "IDLE", "CUDA", "QUEUE_DEAD"))}
    summary = next(f.message for f in analyze(rep) if f.code == "QUEUE_SUMMARY")
    assert "finetune-nightly" in summary and "frozen-eval 2 h ago" in summary


def test_worker_down_with_work_waiting_warns_with_the_fix():
    rep = report(status(queued_eligible=3, worker={"state": "busy", "heartbeat": NOW - 3600}))
    f = next(f for f in analyze(rep) if f.code == "WORKER_DOWN")
    assert f.severity == WARN and "reset-failed" in f.fix and "3 eligible" in f.message


def test_stale_lease_is_reported():
    assert codes(report(status(stale_leases=2, worker={"heartbeat": NOW - 5000})))["QUEUE_STALE_LEASE"] == WARN


def test_cuda_blocked_is_critical_on_the_spark():
    rep = report(status(worker={"state": "cuda-blocked", "heartbeat": NOW - 5, "blocked": "cuda: torch.cuda.is_available() is False"}, queued_eligible=1))
    f = next(f for f in analyze(rep) if f.code == "CUDA_BLOCKED")
    assert f.severity == CRIT and "is_available" in f.message


def test_idle_for_30_minutes_with_eligible_work_warns_but_not_before():
    rep = report(status(queued_eligible=2, last_busy=NOW - 3000, worker={"state": "idle", "heartbeat": NOW - 5, "blocked": "gpu lock held by another job"}))
    f = next(f for f in analyze(rep) if f.code == "IDLE_WITH_WORK")
    assert f.severity == WARN and "gpu lock" in f.message
    assert "IDLE_WITH_WORK" not in codes(report(status(queued_eligible=2, last_busy=NOW - 600)))
    assert "IDLE_WITH_WORK" not in codes(report(status(queued_eligible=2, last_busy=NOW - 3000, paused=True)))


def test_dead_jobs_and_paused_and_not_installed():
    rep = report(status(dead_24h=[{"id": 4, "type": "harvest-crawl", "error": "exit 78: license"}], paused=True))
    found = codes(rep)
    assert found["QUEUE_DEAD_JOBS"] == WARN and found["QUEUE_PAUSED"] == INFO
    assert codes(report("QUEUE_NOT_INSTALLED"))["QUEUE_NOT_INSTALLED"] == INFO
    assert codes(report("QUEUE_NOT_STARTED"))["QUEUE_NOT_STARTED"] == WARN
    assert "QUEUE_BAD_JSON" in codes(report("{not json"))


def test_probe_script_has_the_queue_section_before_the_end_marker():
    probe = (SCRIPTS / "fleet" / "probe.sh").read_text()
    assert probe.index('echo "[queue]"') < probe.index('echo "[end]"')
    assert "queue.py\" status --compact" in probe


# ---- processes: terminate must not wait out the grace period for a dead child ---------------------
def test_terminate_is_quick_and_reaps_the_child(tmp_path):
    h = SubprocessRunner().start([sys.executable, "-c", "import time; time.sleep(120)"], dict(os.environ), str(tmp_path), str(tmp_path / "l.log"))
    started = time.time()
    rc = h.terminate(grace_s=30)
    assert time.time() - started < 5, "SIGTERM'd child is reaped at once, not after the 30 s grace"
    assert rc is not None and h.poll() is not None


# ---- systemd units and the installer --------------------------------------------------------------
def read_unit(name: str) -> str:
    return (UNITS / name).read_text()


def test_worker_unit_has_the_safety_settings():
    u = read_unit("gs-worker.service")
    for needle in ("Type=notify", "WatchdogSec=", "StartLimitBurst=", "StartLimitIntervalSec=", "Restart=on-failure", "RestartSec=",
                   "KillMode=control-group", "MemoryMax=", "CPUQuota=", "TasksMax=", "ExecStartPre=", "ExecStopPost=", "TimeoutStopSec=",
                   "LogRateLimitBurst="):
        assert needle in u, needle
    assert "Restart=always" not in u, "always-restart can become a restart storm"
    burst = int(re.search(r"StartLimitBurst=(\d+)", u).group(1))
    restart = int(re.search(r"RestartSec=(\d+)", u).group(1))
    interval = int(re.search(r"StartLimitIntervalSec=(\d+)", u).group(1))
    assert burst * restart < interval, "the start limit is reachable, so a crash loop stops instead of continuing forever"


def test_revive_timer_is_bounded_hourly():
    assert "OnUnitActiveSec=1h" in read_unit("gs-worker-revive.timer")
    assert "reset-failed" in read_unit("gs-worker-revive.service")


def test_installer_renders_every_unit_without_leftover_placeholders(tmp_path):
    dest = tmp_path / "units"
    r = subprocess.run(["bash", str(SCRIPTS / "fleet" / "install-units.sh"), "--dest", str(dest)], capture_output=True, text=True,
                       env={**os.environ, "GS_MACHINE": "spark"})
    assert r.returncode == 0, r.stderr
    names = {p.name for p in dest.iterdir()}
    assert {"gs-worker.service", "gs-worker-revive.timer", "gs-queue-daily.timer", "gs-fleet-check.timer", "gs-batch.slice"} <= names
    for p in dest.iterdir():
        assert not re.search(r"@[A-Z_]+@", p.read_text()), p.name
    assert str(REPO) in (dest / "gs-worker.service").read_text(), "the unit points at the checkout it was installed from"
    if shutil.which("systemd-analyze"):
        v = subprocess.run(["systemd-analyze", "--user", "verify", str(dest / "gs-worker.service")], capture_output=True, text=True)
        assert "error" not in v.stderr.lower(), v.stderr


@pytest.mark.parametrize("script", [
    "gs_worker.sh", "fleet/boot_check.sh", "fleet/install-units.sh", "fleet/runners/harvest_run.sh", "fleet_status.sh", "gs_run.sh",
])
def test_shell_scripts_parse(script):
    assert subprocess.run(["bash", "-n", str(SCRIPTS / script)], capture_output=True).returncode == 0


def test_manifest_validation_command_passes():
    r = subprocess.run([sys.executable, str(SCRIPTS / "fleet" / "queue.py"), "validate"], capture_output=True, text=True)
    assert r.returncode == 0 and "7 job types" in r.stdout


def test_queue_cli_works_without_the_heavy_package(tmp_path):
    """The CLI must run with only the standard library (the Spark's system python3 has no pydantic)."""
    env = {**os.environ, "GS_STATE_DIR": str(tmp_path), "GS_QUEUE_DB": str(tmp_path / "q.db"), "GS_MACHINE": "mac"}
    r = subprocess.run([sys.executable, "-S", "-c",
                        "import sys, runpy; sys.argv=['queue.py','status']; sys.path.insert(0, %r); runpy.run_path(%r, run_name='__main__')"
                        % (str(SCRIPTS / "fleet"), str(SCRIPTS / "fleet" / "queue.py"))],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "machine mac" in r.stdout


# ---- sharded harvest ------------------------------------------------------------------------------
def test_shard_seeds_partitions_by_host_and_fails_cleanly(tmp_path):
    seeds = tmp_path / "seeds.jsonl"
    urls = [f"https://site{i % 40}.edu/page{i}" for i in range(200)]
    seeds.write_text("\n".join(json.dumps({"url": u, "license": "cc-by"}) for u in urls) + "\n")
    outs = []
    for shard in range(3):
        out = tmp_path / f"s{shard}.jsonl"
        r = subprocess.run([sys.executable, str(SCRIPTS / "fleet" / "shard_seeds.py"), "--seeds", str(seeds), "--shard", str(shard),
                            "--of", "3", "--out", str(out)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        outs.append([json.loads(line)["url"] for line in out.read_text().splitlines()])
    assert sorted(sum(outs, [])) == sorted(urls), "every seed lands in exactly one shard"
    hosts = [{u.split("/")[2] for u in o} for o in outs]
    assert not (hosts[0] & hosts[1] or hosts[0] & hosts[2] or hosts[1] & hosts[2]), "a site is crawled by one shard only"
    missing = subprocess.run([sys.executable, str(SCRIPTS / "fleet" / "shard_seeds.py"), "--seeds", str(tmp_path / "nope.jsonl"),
                              "--shard", "0", "--of", "3", "--out", str(tmp_path / "x")], capture_output=True, text=True)
    assert missing.returncode == 78


def _fake_python(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "fakepy"
    p.write_text(f"#!/bin/sh\n{body}\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def test_harvest_runner_refuses_non_commercial_licenses(tmp_path):
    py = _fake_python(tmp_path, "echo cc-by-nc,cc-by-nc-sa")
    r = subprocess.run(["bash", str(SCRIPTS / "fleet" / "runners" / "harvest_run.sh"), "0", "3", "60"], capture_output=True, text=True,
                       env={**os.environ, "GS_PYTHON": str(py), "HOME": str(tmp_path)})
    assert r.returncode == 78 and "NON-COMMERCIAL" in r.stderr


def test_harvest_runner_continues_when_the_allowlist_is_commercial_safe(tmp_path):
    py = _fake_python(tmp_path, "exit 0")  # the guard prints nothing: no -nc licenses
    r = subprocess.run(["bash", str(SCRIPTS / "fleet" / "runners" / "harvest_run.sh"), "0", "3", "60"], capture_output=True, text=True,
                       env={**os.environ, "GS_PYTHON": str(py), "HOME": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    allow = subprocess.run(["bash", str(SCRIPTS / "fleet" / "runners" / "harvest_run.sh"), "0", "3", "60"], capture_output=True, text=True,
                           env={**os.environ, "GS_PYTHON": str(_fake_python(tmp_path, "echo cc-by-nc"), ), "GS_ALLOW_NC": "1", "HOME": str(tmp_path)})
    assert "NON-COMMERCIAL" not in allow.stderr, "an explicit internal-research override is honored"
