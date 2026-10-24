"""The Spark's systemd units and service scripts under version control: installer, loops, warm-up, CUDA-gated ingest."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
UD = REPO / "scripts" / "fleet" / "spark-units"
SCRIPTS = sorted(UD.glob("*.sh"))
UNIT_NAMES = ["aoep-llm-train", "aoep-voice-train", "aoep-voice-ingest", "aoep-gpu-balance", "aoep-course-translate",
              "aoep-enroll-ui", "aoep-listening-lab"]


def run(cmd, env=None, timeout=60, cwd=None):
    full = {**os.environ, **(env or {})}
    return subprocess.run(cmd, env=full, capture_output=True, text=True, timeout=timeout, cwd=cwd)


# ---- static ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_script_is_valid_bash_and_executable(script):
    assert run(["bash", "-n", str(script)]).returncode == 0
    if script.name != "lib.sh":
        assert os.access(script, os.X_OK), f"{script.name} must be executable"


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_shellcheck_has_no_errors():
    r = run(["shellcheck", "-S", "error", "-x", *map(str, SCRIPTS)])
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("name", UNIT_NAMES)
def test_unit_templates_point_at_existing_scripts_and_use_the_root_placeholder(name):
    text = (UD / "units" / f"{name}.service").read_text()
    assert "[Service]" in text and "ExecStart=@ROOT@/scripts/fleet/spark-units/" in text
    exe = text.split("ExecStart=@ROOT@/", 1)[1].splitlines()[0].strip()
    assert (REPO / exe).is_file(), exe
    assert "/home/nvidia" not in text, "units must not hard-code the user's home: use %h"


def test_the_monitor_unit_gives_the_exit_handler_time_and_logs_to_the_journal():
    text = (UD / "units" / "aoep-gpu-balance.service").read_text()
    assert "KillSignal=SIGTERM" in text and "TimeoutStopSec=20" in text and "StandardOutput=journal" in text


def test_nightly_warms_the_llama_server_before_the_bakeoff():
    text = (REPO / "training" / "spark_nightly.sh").read_text()
    assert text.index("llama-warm.sh") > text.index('echo "== 6/6 bake-off =="')
    assert text.index("llama-warm.sh") < text.index("nightly_candidates.py")
    assert (UD / "llama-warm.sh").is_file()


# ---- installer ------------------------------------------------------------------------------------------
@pytest.fixture()
def box(tmp_path):
    units = tmp_path / "units"
    state = tmp_path / "state"
    units.mkdir()
    fake = tmp_path / "systemctl"
    log = tmp_path / "systemctl.log"
    fake.write_text(f'#!/usr/bin/env bash\necho "$@" >> {log}\n')
    fake.chmod(0o755)
    env = {"SU_UNITS_DIR": str(units), "SU_STATE_DIR": str(state), "SYSTEMCTL": str(fake), "SU_PY": sys.executable,
           "TMPDIR": str(tmp_path)}
    return units, state, log, env


def install(env, *args):
    return run(["bash", str(UD / "install.sh"), *args], env=env)


def seed_live(units: Path):
    (units / "aoep-gpu-balance.service").write_text("[Service]\nExecStart=/old/gpu-balance-monitor.sh\n")
    d = units / "aoep-voice-ingest.service.d"
    d.mkdir()
    (d / "gpu.conf").write_text("[Service]\nEnvironment=AOEP_ASR_DEVICE=cuda\n")


def test_dry_run_is_the_default_and_writes_nothing(box):
    units, state, log, env = box
    seed_live(units)
    before = {p: p.read_text() for p in units.rglob("*") if p.is_file()}
    r = install(env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DRY RUN" in r.stdout and "CHANGED  aoep-gpu-balance.service" in r.stdout
    assert "NEW      aoep-llm-train.service" in r.stdout and "RETIRE   aoep-voice-ingest.service.d/gpu.conf" in r.stdout
    assert "-ExecStart=/old/gpu-balance-monitor.sh" in r.stdout               # a real diff against the live unit
    assert {p: p.read_text() for p in units.rglob("*") if p.is_file()} == before
    assert not state.exists() and not log.exists()


def test_apply_installs_backs_up_retires_and_never_restarts(box):
    units, state, log, env = box
    seed_live(units)
    r = install(env, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    for n in ["aoep-llm-train", "aoep-voice-train", "aoep-voice-ingest", "aoep-gpu-balance", "aoep-enroll-ui", "aoep-listening-lab"]:
        text = (units / f"{n}.service").read_text()
        assert "@ROOT@" not in text and str(REPO) in text
    assert not (units / "aoep-course-translate.service").exists()             # legacy: only with --with-legacy-translate
    assert (units / "aoep-voice-ingest.service.d" / "10-spark-units.conf").is_file()
    assert not (units / "aoep-voice-ingest.service.d" / "gpu.conf").exists()   # retired
    backups = list(state.glob("backup-*"))
    assert len(backups) == 1
    assert "/old/gpu-balance-monitor.sh" in (backups[0] / "aoep-gpu-balance.service").read_text()
    assert "AOEP_ASR_DEVICE=cuda" in (backups[0] / "aoep-voice-ingest.service.d" / "gpu.conf").read_text()
    calls = log.read_text().splitlines()
    assert calls == ["daemon-reload"]                                         # no enable, no restart
    assert "ROLLBACK" in r.stdout and str(backups[0]) in r.stdout
    assert f"rm -f {units}/aoep-llm-train.service" in r.stdout            # a file that was new: rollback removes it
    assert f"rm -f {units}/aoep-gpu-balance.service" not in r.stdout     # a file that was replaced: rollback restores it


def test_apply_is_idempotent(box):
    units, state, log, env = box
    seed_live(units)
    assert install(env, "--apply").returncode == 0
    snapshot = {p: p.read_text() for p in units.rglob("*") if p.is_file()}
    log.unlink()
    r = install(env, "--apply")
    assert "Nothing to change" in r.stdout
    assert {p: p.read_text() for p in units.rglob("*") if p.is_file()} == snapshot
    assert not log.exists() and len(list(state.glob("backup-*"))) == 1


def test_restart_and_enable_only_when_asked(box):
    units, state, log, env = box
    r = install(env, "--apply", "--restart", "aoep-gpu-balance", "--enable", "aoep-gpu-balance.service")
    assert r.returncode == 0, r.stdout
    calls = log.read_text().splitlines()
    assert "enable aoep-gpu-balance.service" in calls and "restart aoep-gpu-balance.service" in calls
    assert not any("llm-train" in c for c in calls)


def test_restarting_the_training_loop_prints_a_warning(box):
    _, _, _, env = box
    r = install(env, "--apply", "--restart", "aoep-llm-train")
    assert "WARNING  restarting aoep-llm-train" in r.stdout


def test_root_option_points_the_units_at_a_chosen_worktree(box, tmp_path):
    units, state, log, env = box
    other = tmp_path / "gs-wt" / "main-current"
    (other / "scripts").mkdir(parents=True)
    (other / "packages" / "shared" / "src").mkdir(parents=True)
    shutil.copytree(REPO / "packages" / "shared" / "src" / "aoep_shared", other / "packages" / "shared" / "src" / "aoep_shared")
    r = install(env, "--apply", "--root", str(other))
    assert r.returncode == 0, r.stdout
    assert f"ExecStart={other}/scripts/fleet/spark-units/llm-forever.sh" in (units / "aoep-llm-train.service").read_text()


def test_legacy_translate_unit_only_with_its_flag(box):
    units, _, _, env = box
    assert install(env, "--apply", "--with-legacy-translate").returncode == 0
    assert (units / "aoep-course-translate.service").is_file()


def test_preflight_failure_blocks_apply(box, tmp_path):
    units, state, log, env = box
    empty_root = tmp_path / "no-monitor-here"          # a worktree that does not contain aoep_shared.spark_balance
    empty_root.mkdir()
    dry = install(env, "--root", str(empty_root))
    assert "FAIL  the monitor does not import" in dry.stdout and dry.returncode == 0   # a dry run only reports
    r = install(env, "--apply", "--root", str(empty_root))
    assert r.returncode == 1 and "preflight failed" in r.stdout
    assert not list(units.glob("*.service")) and not log.exists()


# ---- llm-forever.sh -------------------------------------------------------------------------------------
def fake_worktree(tmp_path, nightly_body):
    wt = tmp_path / "wt"
    (wt / "training").mkdir(parents=True)
    nightly = wt / "training" / "spark_nightly.sh"
    nightly.write_text("#!/usr/bin/env bash\n" + nightly_body)
    nightly.chmod(0o755)
    return wt


def test_hold_file_stops_new_cycles_and_is_logged_once(tmp_path):
    wt = fake_worktree(tmp_path, f'echo ran >> {tmp_path}/ran.log\n')
    hold = tmp_path / "hold"
    hold.write_text("frozen at 20.4%\n")
    env = {"AOEP_TRAIN_WORKTREE": str(wt), "GS_STEM_HOLD_FILE": str(hold), "AOEP_FOREVER_ONCE": "1"}
    r = run(["bash", str(UD / "llm-forever.sh")], env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "STEM training held by" in r.stdout and "frozen at 20.4%" in r.stdout
    assert r.stdout.count("held by") == 1
    assert not (tmp_path / "ran.log").exists()
    hold.unlink()
    r = run(["bash", str(UD / "llm-forever.sh")], env)
    assert (tmp_path / "ran.log").read_text() == "ran\n"
    assert "llm cycle start" in r.stdout and "llm cycle exit=0" in r.stdout


def test_sigterm_ends_the_loop_cleanly_and_leaves_no_orphans(tmp_path):
    pidfile = tmp_path / "nightly.pid"
    wt = fake_worktree(tmp_path, f'echo $$ > {pidfile}\nsleep 300 &\nsleep 300 &\nwait\n')
    env = {**os.environ, "AOEP_TRAIN_WORKTREE": str(wt), "GS_STEM_HOLD_FILE": str(tmp_path / "nohold"), "AOEP_STOP_GRACE_S": "5"}
    proc = subprocess.Popen(["bash", str(UD / "llm-forever.sh")], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, start_new_session=True)
    try:
        deadline = time.time() + 20
        while time.time() < deadline and not pidfile.exists():
            time.sleep(0.1)
        assert pidfile.exists(), "the nightly never started"
        time.sleep(0.5)
        nightly_pgid = int(pidfile.read_text())
        os.kill(proc.pid, signal.SIGTERM)
        out, _ = proc.communicate(timeout=30)
        assert proc.returncode == 0, out
        time.sleep(0.3)
        with pytest.raises(ProcessLookupError):
            os.killpg(nightly_pgid, 0)          # nothing is left in the nightly's process group
        assert "llm loop stopped" in out
    finally:
        if proc.poll() is None:
            proc.kill()


def test_a_failed_cycle_sleeps_before_retrying(tmp_path):
    wt = fake_worktree(tmp_path, "exit 3\n")
    env = {"AOEP_TRAIN_WORKTREE": str(wt), "GS_STEM_HOLD_FILE": str(tmp_path / "nohold"), "AOEP_FOREVER_ONCE": "1"}
    r = run(["bash", str(UD / "llm-forever.sh")], env)
    assert "llm cycle exit=3" in r.stdout and r.returncode == 0


# ---- llama-warm.sh ---------------------------------------------------------------------------------------
class Llama(BaseHTTPRequestHandler):
    sleeping = False
    chat_status = 200
    hits: list = []

    def log_message(self, *a):  # silence
        pass

    def _send(self, code, body="{}"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        Llama.hits.append(("GET", self.path))
        if self.path == "/health":
            self._send(200, '{"status":"ok"}')
        elif self.path == "/props":
            self._send(200, json.dumps({"is_sleeping": Llama.sleeping}))
        else:
            self._send(404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode()
        Llama.hits.append(("POST", self.path, body))
        if Llama.sleeping:
            Llama.sleeping = False                 # a request wakes the server
        self._send(Llama.chat_status, '{"choices":[{"message":{"content":"OK"}}]}')


@pytest.fixture()
def llama():
    Llama.sleeping, Llama.chat_status, Llama.hits = False, 200, []
    srv = HTTPServer(("127.0.0.1", 0), Llama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_warm_sends_a_one_token_request_to_an_awake_server(llama):
    r = run(["bash", str(UD / "llama-warm.sh"), "--url", llama + "/v1", "--model", "m"])
    assert r.returncode == 0, r.stdout
    posts = [h for h in Llama.hits if h[0] == "POST"]
    assert len(posts) == 1 and posts[0][1] == "/v1/chat/completions"
    body = json.loads(posts[0][2])
    assert body["max_tokens"] == 1 and body["model"] == "m"
    assert "warm: model answered" in r.stdout


def test_warm_wakes_a_sleeping_server(llama):
    Llama.sleeping = True
    r = run(["bash", str(UD / "llama-warm.sh"), "--url", llama])
    assert "server is sleeping: waking it" in r.stdout and "warm: model answered" in r.stdout
    assert Llama.sleeping is False


def test_warm_is_best_effort_unless_strict(llama):
    dead = "http://127.0.0.1:9"                    # nothing listens on the discard port
    assert run(["bash", str(UD / "llama-warm.sh"), "--url", dead]).returncode == 0
    assert run(["bash", str(UD / "llama-warm.sh"), "--url", dead, "--strict"]).returncode == 1
    Llama.chat_status = 500
    assert run(["bash", str(UD / "llama-warm.sh"), "--url", llama]).returncode == 0
    r = run(["bash", str(UD / "llama-warm.sh"), "--url", llama, "--strict"])
    assert r.returncode == 1 and "warm-up request failed" in r.stdout


# ---- voice-ingest-forever.sh -----------------------------------------------------------------------------
def fake_ingest_root(tmp_path, cuda_ok: bool, policy_workers: int):
    root = tmp_path / "root"
    pkg = root / "packages" / "shared" / "src" / "aoep_shared"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "devices.py").write_text(textwrap.dedent(f"""
        def cuda_smoke():
            return ({cuda_ok}, {'ok' if cuda_ok else 'no kernel image for sm_121'!r})
    """))
    (root / "training").mkdir()
    (root / "training" / "reboot_policy.py").write_text(
        f"def ingest_workers(free_mb, training_alive):\n    return {policy_workers}\n")
    (root / "scripts").mkdir()
    ingest = root / "scripts" / "cosyvoice_batch_ingest.py"
    ingest.write_text(textwrap.dedent(f"""
        import os, sys
        with open({str(tmp_path / 'ingest.log')!r}, 'a') as fh:
            fh.write(' '.join(sys.argv[1:]) + ' device=' + os.environ.get('AOEP_ASR_DEVICE', 'unset') + '\\n')
    """))
    venv = tmp_path / "venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)
    return root, tmp_path / "venv"


def ingest_env(root, venv, **extra):
    return {"AOEP_INGEST_ROOT": str(root), "AOEP_VENV": str(venv), "AOEP_FOREVER_ONCE": "1", **extra}


def test_ingest_exports_cuda_only_when_the_policy_passes_and_caps_workers(tmp_path):
    root, venv = fake_ingest_root(tmp_path, cuda_ok=True, policy_workers=2)
    r = run(["bash", str(UD / "voice-ingest-forever.sh")], ingest_env(root, venv))
    assert r.returncode == 0, r.stdout + r.stderr
    lines = (tmp_path / "ingest.log").read_text().splitlines()
    assert len(lines) == 2 and all("--workers 1" in ln and ln.endswith("device=cuda") for ln in lines)   # policy said 2, cap is 1
    r = run(["bash", str(UD / "voice-ingest-forever.sh")], ingest_env(root, venv, AOEP_INGEST_MAX_WORKERS="2"))
    assert "--workers 2" in (tmp_path / "ingest.log").read_text().splitlines()[-1]


def test_ingest_never_falls_back_to_the_cpu_silently(tmp_path):
    root, venv = fake_ingest_root(tmp_path, cuda_ok=False, policy_workers=1)
    r = run(["bash", str(UD / "voice-ingest-forever.sh")], ingest_env(root, venv))
    assert r.returncode == 0
    assert "CUDA policy failed (no kernel image for sm_121); not starting the ingest on the CPU" in r.stdout
    assert not (tmp_path / "ingest.log").exists()


# ---- legacy translate ------------------------------------------------------------------------------------
def test_legacy_translate_loop_refuses_to_run_unless_explicitly_enabled(tmp_path):
    r = run(["bash", str(UD / "translate-forever.sh")], {"HOME": str(tmp_path)})
    assert r.returncode == 0 and "legacy translate loop is retired" in r.stdout


# ---- lib.sh ---------------------------------------------------------------------------------------------
def test_su_run_child_returns_the_childs_status_and_sleep_is_interruptible(tmp_path):
    script = tmp_path / "t.sh"
    script.write_text(textwrap.dedent(f"""
        . {UD}/lib.sh
        su_run_child bash -c 'exit 7'
        echo "rc=$?"
        ( sleep 0.3; kill -TERM $$ ) &
        t0=$(date +%s)
        su_sleep 30
        echo "slept=$(( $(date +%s) - t0 )) stop=$SU_STOP"
    """))
    r = run(["bash", str(script)])
    assert "rc=7" in r.stdout
    assert "slept=0" in r.stdout or "slept=1" in r.stdout
    assert "stop=1" in r.stdout


# ---- the two lab units ------------------------------------------------------------------------------------
@pytest.mark.parametrize("name,port", [("aoep-enroll-ui", "8780"), ("aoep-listening-lab", "8790")])
def test_lab_units_are_small_restarting_and_never_enabled_by_the_installer(name, port):
    text = (UD / "units" / f"{name}.service").read_text()
    assert "MemoryMax=2G" in text and "Restart=always" in text and "MemorySwapMax=0" in text
    launcher = (UD / text.split("ExecStart=@ROOT@/scripts/fleet/spark-units/", 1)[1].splitlines()[0].strip()).read_text()
    assert port in launcher and "0.0.0.0" not in launcher and "0.0.0.0" not in text


def fake_python(tmp_path):
    venv = tmp_path / "venv" / "bin"
    venv.mkdir(parents=True)
    py = venv / "python"
    py.write_text("#!/bin/bash\necho \"ARGS: $*\" > \"$FAKE_PY_LOG\"\n")
    py.chmod(0o755)
    return tmp_path / "venv"


def test_enroll_ui_launcher_serves_the_voices_dir_on_8780(tmp_path):
    log = tmp_path / "py.log"
    r = run(["bash", str(UD / "enroll-ui.sh")], env={"AOEP_VENV": str(fake_python(tmp_path)), "FAKE_PY_LOG": str(log),
                                                    "AOEP_VOICES_DIR": str(tmp_path / "v"), "HOME": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    assert f"-m tts_bakeoff.voice_clone.enroll_ui --root {tmp_path / 'v'} --port 8780" in log.read_text()
    assert (tmp_path / "v").is_dir()


def test_lab_launcher_serves_the_newest_clones_folder_without_opening_a_browser(tmp_path):
    root = tmp_path / "root"
    for d in ("2026-10-23-clones", "2026-10-25-clones", "2026-10-26-voices"):
        (root / "runs" / d).mkdir(parents=True)
    log = tmp_path / "py.log"
    env = {"AOEP_VENV": str(fake_python(tmp_path)), "FAKE_PY_LOG": str(log), "AOEP_LAB_ROOT": str(root), "HOME": str(tmp_path)}
    assert run(["bash", str(UD / "listening-lab.sh")], env=env).returncode == 0
    args = log.read_text()
    assert "--port 8790" in args and "--no-open" in args and f"--out {root}/runs/2026-10-25-clones" in args
    env["AOEP_LAB_OUT"] = str(tmp_path)
    assert run(["bash", str(UD / "listening-lab.sh")], env=env).returncode == 0
    assert f"--out {tmp_path}" in log.read_text()


def test_uninstall_is_a_dry_run_by_default_and_only_touches_the_lab_units(box):
    units, state, log, env = box
    for n in ("aoep-enroll-ui", "aoep-listening-lab", "aoep-llm-train"):
        (units / f"{n}.service").write_text("[Service]\nExecStart=/x\n")
    uninstall = UD / "uninstall.sh"
    r = run(["bash", str(uninstall)], env=env)
    assert "WOULD REMOVE aoep-enroll-ui.service" in r.stdout and "DRY RUN" in r.stdout
    assert (units / "aoep-enroll-ui.service").exists()
    r = run(["bash", str(uninstall), "--apply"], env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (units / "aoep-enroll-ui.service").exists() and not (units / "aoep-listening-lab.service").exists()
    assert (units / "aoep-llm-train.service").exists()                    # training is never touched by default
    assert list(state.glob("backup-*/aoep-enroll-ui.service"))
    calls = log.read_text().splitlines()
    assert "stop aoep-enroll-ui.service" in calls and "disable aoep-listening-lab.service" in calls and calls[-1] == "daemon-reload"
