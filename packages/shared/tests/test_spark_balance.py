"""The Spark balance monitor's decisions, against fake machines (and one real SIGSTOP/SIGCONT round trip)."""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from aoep_shared import spark_balance as sb
from aoep_shared.spark_balance import Config, Monitor, Sample, State, System, classify, step

SRC = str(Path(sb.__file__).resolve().parents[1])


# ---- classification ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("cmd,kind", [
    ("/x/.venv/bin/python training/evaluate.py --offline --device cuda --base-model /m", "eval"),
    ("python3 training/run_finetune.py --config c.yaml", "finetune"),
    ("/home/nvidia/.venv/bin/python /repo/cosyvoice/bin/train.py --model llm", "finetune"),
    ("bash ./scripts/spark_cosyvoice_khmer_train.sh", "finetune"),
    ("python training/nightly_candidates.py --serve-url http://127.0.0.1:8342/v1", "bakeoff"),
    ("python scripts/spark_serve_eval.py --port 8342", "bakeoff"),
    ("flock /home/nvidia/.gs-gpu.lock env GS_GPU_LOCK_HELD=1 ./training/spark_nightly.sh", "other"),
    ("llama-server --model /tmp/qwen.gguf --port 8342", "other"),
    ("python -m aoep_shared.spark_balance", "other"),
    ("python training/retrain.py", "other"),          # not train.py
    ("python training/evaluate_all.py", "other"),     # not evaluate.py
])
def test_classify_by_command_line_not_gpu_memory(cmd, kind):
    assert classify(cmd) == kind


# ---- pure decision logic ----------------------------------------------------------------------------------
CFG = Config(window_s=180, grace_s=600, kill_floor_mb=24576, critical_mb=6144, starve_tok_s=0.25)


def sample(now, free=20000, finetune=(1,), evals=(), bake=(9,), server="ok", slots=True, decoded=0):
    return Sample(now=now, free_mb=free, finetune_pids=list(finetune), eval_pids=list(evals), bakeoff_pids=list(bake),
                  server=server, slots_ok=slots, decoded=decoded)


def kinds(acts):
    return [a[0] for a in acts]


def run_seq(samples, cfg=CFG, st=None):
    st = st or State()
    out = []
    for s in samples:
        out.append(kinds(step(st, cfg, s)))
    return st, out


def test_a_starved_bakeoff_is_stopped_only_when_everything_agrees():
    # server up for a long time (no wake), fine-tune running, memory short, first token at t=0, still 10 tokens at t=200
    st = State()
    step(st, CFG, sample(0, decoded=5))                       # first token: window opens (first observation: no grace)
    acts = step(st, CFG, sample(200, decoded=15))             # 10 tokens in 200 s = 0.05 tok/s over a full window
    stop = [a for a in acts if a[0] == "stop_bakeoff"]
    assert len(stop) == 1
    assert stop[0][1]["reason"] == "starved_by_finetune"
    assert stop[0][1]["pids"] == [9]


def test_evaluation_is_not_a_finetune_so_the_bakeoff_is_spared():
    st = State()
    step(st, CFG, sample(0, finetune=(), evals=(7,), decoded=5))
    acts = step(st, CFG, sample(200, finetune=(), evals=(7,), decoded=6))
    assert "stop_bakeoff" not in kinds(acts)
    assert [a[1]["why"] for a in acts if a[0] == "log"] == ["evaluation_not_finetune"]


def test_memory_floor_a_starved_bakeoff_with_plenty_of_memory_is_spared():
    st = State()
    step(st, CFG, sample(0, free=70000, decoded=5))
    acts = step(st, CFG, sample(200, free=70000, decoded=6))
    assert "stop_bakeoff" not in kinds(acts)
    assert [a[1]["why"] for a in acts if a[0] == "log"] == ["memory_not_short"]
    # the same situation with memory under the floor stops it
    st2 = State()
    step(st2, CFG, sample(0, free=20000, decoded=5))
    assert "stop_bakeoff" in kinds(step(st2, CFG, sample(200, free=20000, decoded=6)))


def test_critical_memory_stops_it_even_during_an_evaluation():
    acts = step(State(), CFG, sample(0, free=4000, finetune=(), evals=(7,), decoded=0))
    stop = [a for a in acts if a[0] == "stop_bakeoff"]
    assert stop and stop[0][1]["reason"] == "memory_critical"


def test_nothing_is_measured_until_the_first_token():
    # a reloading / prompt-processing server decodes nothing: no window, no kill, however long it takes
    st = State()
    for t in (0, 100, 300, 600, 1200):
        assert "stop_bakeoff" not in kinds(step(st, CFG, sample(t, decoded=0)))
    assert st.win_start is None
    step(st, CFG, sample(1300, decoded=1))                  # first token: now the window opens
    assert st.win_start == 1300
    assert "stop_bakeoff" not in kinds(step(st, CFG, sample(1400, decoded=1)))   # window not long enough yet
    assert "stop_bakeoff" in kinds(step(st, CFG, sample(1500, decoded=2)))       # 180 s elapsed, 0.005 tok/s


def test_not_ready_server_is_never_judged():
    for server, slots in (("loading", False), ("sleeping", False), ("down", False), ("ok", False)):
        st = State()
        for t in (0, 200, 400):
            assert "stop_bakeoff" not in kinds(step(st, CFG, sample(t, server=server, slots=slots, decoded=3)))


def test_wake_grants_grace_after_sleeping_loading_ready():
    st = State()
    step(st, CFG, sample(0, server="sleeping", slots=False))
    step(st, CFG, sample(20, server="loading", slots=False))
    acts = step(st, CFG, sample(40, server="ok", decoded=2))   # ready again: wake detected
    assert [a[1]["event"] for a in acts if a[0] == "log"][0] == "server_woke"
    assert st.grace_until == pytest.approx(40 + 600)
    # starved for a full window but still inside the grace period: spared
    acts = step(st, CFG, sample(300, decoded=3))
    assert "stop_bakeoff" not in kinds(acts)
    assert [a[1]["why"] for a in acts if a[0] == "log"] == ["grace"]
    # grace ends at t=640: the same starvation now counts, at the first sample after it
    acts = step(st, CFG, sample(700, decoded=4))
    stop = [a for a in acts if a[0] == "stop_bakeoff"]
    assert stop and stop[0][1]["reason"] == "starved_by_finetune" and stop[0][1]["in_grace"] is False
    assert st.win_start is None                                # the window restarts after a stop


def test_no_grace_when_the_monitor_first_sees_an_awake_server():
    st = State()
    step(st, CFG, sample(0, decoded=5))
    assert st.grace_until == 0.0


def test_a_new_request_restarts_the_window():
    st = State()
    step(st, CFG, sample(0, decoded=500))
    step(st, CFG, sample(100, decoded=20))      # counter went down: a new generation began
    assert st.win_start == 100 and st.win_base == 20


def test_fast_decoding_is_not_starved():
    st = State()
    step(st, CFG, sample(0, decoded=10))
    acts = step(st, CFG, sample(200, decoded=10 + 200 * 3))   # 3 tok/s
    assert "stop_bakeoff" not in kinds(acts)


def test_slots_unreachable_disables_the_rate_rule_and_says_so_once():
    st = State()
    first = step(st, CFG, sample(0, slots=False, decoded=0))
    again = step(st, CFG, sample(20, slots=False, decoded=0))
    assert any(a[1].get("event") == "slots_unreachable" for a in first)
    assert not any(a[1].get("event") == "slots_unreachable" for a in again)


def test_ingest_pause_and_resume_thresholds():
    assert kinds(step(State(), CFG, sample(0, free=9000, bake=()))) == ["pause_ingest"]
    assert kinds(step(State(), CFG, sample(0, free=12000, bake=()))) == []          # between the two: no change
    assert kinds(step(State(), CFG, sample(0, free=20000, bake=()))) == ["resume_ingest"]


def test_no_bakeoff_client_nothing_to_stop():
    assert "stop_bakeoff" not in kinds(step(State(), CFG, sample(0, free=100, bake=())))


def test_config_reads_the_environment(monkeypatch):
    monkeypatch.setenv("BALANCE_GRACE_S", "30")
    monkeypatch.setenv("BALANCE_STARVE_TOK_S", "1.5")
    monkeypatch.setenv("BALANCE_BAKEOFF_PATTERN", "my_client\\.py")
    cfg = Config.from_env()
    assert cfg.grace_s == 30 and cfg.starve_tok_s == 1.5 and cfg.bakeoff_pattern == "my_client\\.py"
    monkeypatch.setenv("BALANCE_GRACE_S", "junk")
    assert Config.from_env().grace_s == Config.grace_s


# ---- the monitor around a fake machine --------------------------------------------------------------------
class FakeSystem(System):
    def __init__(self):
        self.t = 1000.0
        self.mem = 60000
        self.procs = []
        self.http = {}
        self.sent = []
        self.starts = {}
        self.gpu = "0,[N/A]"

    def now(self): return self.t
    def free_mb(self): return self.mem
    def ps(self): return list(self.procs)
    def gpu_line(self): return self.gpu
    def http_get(self, url, timeout=3.0):
        return self.http.get(url.split("8342", 1)[-1], (None, ""))
    def send(self, pid, sig):
        self.sent.append((pid, sig))
        return True
    def starttime(self, pid): return self.starts.get(pid)


def serve(fs, sleeping=False, health=200, slots=200, decoded=0):
    fs.http = {
        "/props": (200, json.dumps({"is_sleeping": sleeping})),
        "/health": (health, "{}"),
        "/slots": (slots, json.dumps([{"is_processing": decoded > 0, "next_token": [{"n_decoded": decoded}]}])),
    }


class Events(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(json.loads(record.getMessage()))


def make_monitor(tmp_path, fs, cfg=CFG):
    lg = logging.getLogger(f"t.{id(fs)}")
    lg.handlers.clear()
    lg.propagate = False
    ev = Events()
    lg.addHandler(ev)
    lg.setLevel(logging.INFO)
    return Monitor(fs, cfg, tmp_path, lg), ev


def test_probe_server_states():
    fs = FakeSystem()
    serve(fs, sleeping=True)
    assert sb.probe_server(fs, "http://127.0.0.1:8342") == ("sleeping", False, 0)
    serve(fs, health=503)
    assert sb.probe_server(fs, "http://127.0.0.1:8342") == ("loading", False, 0)
    fs.http = {}
    assert sb.probe_server(fs, "http://127.0.0.1:8342") == ("down", False, 0)
    serve(fs, decoded=42)
    assert sb.probe_server(fs, "http://127.0.0.1:8342") == ("ok", True, 42)
    serve(fs, slots=501)
    assert sb.probe_server(fs, "http://127.0.0.1:8342") == ("ok", False, 0)


def test_monitor_tick_classifies_processes_and_stops_only_the_bakeoff(tmp_path):
    fs = FakeSystem()
    fs.mem = 15000
    fs.procs = [(11, "python training/run_finetune.py"), (12, "python training/evaluate.py"),
                (13, "python training/nightly_candidates.py --serve-url x"), (14, "llama-server --port 8342")]
    serve(fs, decoded=5)
    mon, ev = make_monitor(tmp_path, fs)
    mon.tick()
    fs.t += 200
    serve(fs, decoded=6)
    mon.tick()
    assert (13, signal.SIGTERM) in fs.sent
    assert all(pid == 13 for pid, _ in fs.sent)                 # nothing else was touched
    stopped = [e for e in ev.records if e["event"] == "bakeoff_stopped"]
    assert stopped and stopped[0]["reason"] == "starved_by_finetune" and stopped[0]["finetune"] is True


def test_status_files_are_written_atomically_and_parse(tmp_path):
    fs = FakeSystem()
    fs.procs = [(11, "python training/evaluate.py")]
    serve(fs)
    mon, _ = make_monitor(tmp_path, fs)
    mon.tick()
    doc = json.loads((tmp_path / "balance.status.json").read_text())
    assert doc["eval_pids"] == [11] and doc["free_mb"] == 60000 and doc["server"] == "ok"
    legacy = (tmp_path / "balance.status").read_text()
    assert "free_mb=60000" in legacy and "eval=11" in legacy
    assert not list(tmp_path.glob("*.tmp"))


def test_low_memory_pauses_ingest_and_remembers_it_across_a_restart(tmp_path):
    fs = FakeSystem()
    fs.mem = 8000
    fs.procs = [(21, "yt-dlp -f bestaudio https://x"), (22, "python something_else.py")]
    fs.starts = {21: 111, 22: 222}
    mon, ev = make_monitor(tmp_path, fs)
    mon.tick()
    assert (21, signal.SIGSTOP) in fs.sent and (22, signal.SIGSTOP) not in fs.sent
    assert json.loads((tmp_path / "balance.paused.json").read_text())[0]["pid"] == 21
    # a restarted monitor (or a crash: nothing was resumed) finds the list and resumes when memory recovers
    fs2 = FakeSystem()
    fs2.mem = 40000
    fs2.starts = {21: 111}
    mon2, ev2 = make_monitor(tmp_path, fs2)
    assert [e["pid"] for e in mon2.paused] == [21]
    mon2.tick()
    assert (21, signal.SIGCONT) in fs2.sent
    assert json.loads((tmp_path / "balance.paused.json").read_text()) == []


def test_a_reused_pid_is_never_continued(tmp_path):
    fs = FakeSystem()
    fs.mem = 8000
    fs.procs = [(21, "yt-dlp x")]
    fs.starts = {21: 111}
    mon, _ = make_monitor(tmp_path, fs)
    mon.tick()
    fs.sent.clear()
    fs.starts = {21: 999}          # same PID, different process now
    fs.mem = 40000
    mon.tick()
    assert fs.sent == []


def test_run_always_resumes_what_it_stopped_when_it_exits(tmp_path):
    fs = FakeSystem()
    fs.mem = 8000
    fs.procs = [(21, "yt-dlp x")]
    fs.starts = {21: 5}
    mon, ev = make_monitor(tmp_path, fs)
    ticks = {"n": 0}

    def should_stop():
        ticks["n"] += 1
        return ticks["n"] > 2

    mon.run(should_stop, sleep=lambda s: None)
    assert (21, signal.SIGSTOP) in fs.sent
    assert (21, signal.SIGCONT) in fs.sent                      # resumed in the finally block
    assert fs.sent.index((21, signal.SIGSTOP)) < fs.sent.index((21, signal.SIGCONT))
    assert [e["event"] for e in ev.records][-1] == "monitor_stop"


def test_a_bad_sample_does_not_kill_the_monitor(tmp_path):
    fs = FakeSystem()
    mon, ev = make_monitor(tmp_path, fs)

    def boom():
        raise RuntimeError("nvidia-smi exploded")

    mon.sys.free_mb = boom   # type: ignore[assignment]
    n = {"i": 0}
    mon.run(lambda: (n.__setitem__("i", n["i"] + 1) or n["i"] > 2), sleep=lambda s: None)
    assert any(e["event"] == "tick_error" for e in ev.records)


def test_the_json_log_rotates(tmp_path):
    fs = FakeSystem()
    cfg = Config(log_max_bytes=600, log_backups=2)
    mon = Monitor(fs, cfg, tmp_path)
    for i in range(80):
        mon.emit("tick", n=i, payload="x" * 40)
    names = sorted(p.name for p in tmp_path.glob("balance.jsonl*"))
    assert "balance.jsonl" in names and "balance.jsonl.1" in names and "balance.jsonl.3" not in names
    for line in (tmp_path / "balance.jsonl").read_text().splitlines():
        assert json.loads(line)["event"] == "tick"


# ---- the real thing: SIGSTOP a real process, then make sure SIGTERM on the monitor continues it --------------
def stat_of(pid):
    return subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_real_process_is_stopped_and_continued_when_the_monitor_gets_sigterm(tmp_path):
    child = subprocess.Popen(["bash", "-c", "exec -a yt-dlp-fake sleep 300"])
    driver = tmp_path / "driver.py"
    driver.write_text(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {SRC!r})
        from aoep_shared import spark_balance as sb

        class Low(sb.System):
            def free_mb(self): return 1500          # low memory: pause the ingest
            def http_get(self, url, timeout=3.0): return None, ""
            def gpu_line(self): return "n/a"

        sb.System = Low
        raise SystemExit(sb.main(["--dir", {str(tmp_path)!r}]))
    """))
    env = {**os.environ, "BALANCE_TICK_S": "1", "BALANCE_INGEST_PATTERN": "yt-dlp-fake"}
    mon = subprocess.Popen([sys.executable, str(driver)], env=env, stdout=subprocess.DEVNULL)
    try:
        deadline = time.time() + 15
        while time.time() < deadline and not stat_of(child.pid).startswith("T"):
            time.sleep(0.2)
        assert stat_of(child.pid).startswith("T"), "the monitor never paused the ingest process"
        mon.send_signal(signal.SIGTERM)
        assert mon.wait(timeout=15) == 0
        time.sleep(0.3)
        assert not stat_of(child.pid).startswith("T"), "the process was left stopped after the monitor exited"
        assert json.loads((tmp_path / "balance.paused.json").read_text()) == []
    finally:
        mon.kill() if mon.poll() is None else None
        child.kill()
        child.wait()
