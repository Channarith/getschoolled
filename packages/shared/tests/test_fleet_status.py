"""Parser and rules for scripts/fleet/probe.sh reports (no ssh, no machines needed)."""
import json
import subprocess
import sys
from pathlib import Path

from aoep_shared.fleet_status import (
    CRIT, WARN, analyze, main, parse_budgets, parse_etime, parse_ps_line, parse_report, render,
)

REPO = Path(__file__).resolve().parents[3]

# Modeled on the real Spark output: GB10 with N/A memory, a pinned uvicorn, 38 load, no timers.
SPARK = """FLEET_PROBE 1
host=Chans-Spark
os=Linux
arch=aarch64
now=1792827000
load=38.73 38.20 37.93
mem_total_kb=126976000
mem_avail_kb=61000000
swap_used_kb=0
cpus=20
disk=/ 3900000000 1000000000 2700000000 27
gpu=NVIDIA GB10|0|[N/A]|[N/A]|54
gpu_app=537298|176
[procs_cpu]
nvidia 674839 672963 Sl+ 1-13:52:40 762 3644752 /home/nvidia/code/getschoolled/.venv/bin/python3 /home/nvidia/code/getschoolled/.venv/bin/uvicorn speech_gw.main:app --port 8002
nvidia 3068016 1 SNl 02:14:07 254 27856832 /home/nvidia/code/getschoolled/.venv/bin/python3 scripts/cosyvoice_ingest.py --language zh
root 5186 1 Sl 1-20:04:10 149 29214336 llama-server --model qwen
[procs_rss]
root 5186 1 Sl 1-20:04:10 149 29214336 llama-server --model qwen
nvidia 3068016 1 SNl 02:14:07 254 27856832 /home/nvidia/code/getschoolled/.venv/bin/python3 scripts/cosyvoice_ingest.py --language zh
[zombies]
nvidia 538549 4242 Z 1-02:00:00 0.0 0 [cursor] <defunct>
[zombie_parents]
nvidia 4242 1 Sl 1-03:00:00 0.1 90000 /usr/share/cursor/cursor
[orphans]
nvidia 3068016 1 SNl 02:14:07 254 27856832 /home/nvidia/code/getschoolled/.venv/bin/python3 scripts/cosyvoice_ingest.py --language zh
[lock]
path=/home/nvidia/.gs-gpu.lock
exists=no
[jobs]
[cosyvoice]
{"running": true, "phase": "ingest", "queued": 78, "done": 10, "failed": 1, "last_error": "oom"}
mtime=1792826000
[batch_logs]
[timers]
[end]
"""

KALEL = """FLEET_PROBE 1
host=Kal-el
os=Linux
now=1792827000
load=0.07 0.20 0.18
mem_total_kb=31457280
mem_avail_kb=26000000
swap_used_kb=0
cpus=16
disk=/ 1400000000 204000000 1100000000 16
gpu=NVIDIA GeForce RTX 5060 Ti|2|1200|8151|45
[procs_cpu]
cvanthin 8892 1 Ssl 1-19:00:00 4.4 554660 /usr/bin/gnome-shell --mode=ubuntu
[procs_rss]
[zombies]
[zombie_parents]
[orphans]
[lock]
path=/home/cvanthin/.gs-gpu.lock
exists=yes
holders=
owner=999999 job-x idle 1792000000
owner_alive=no
[jobs]
{"id": "j1", "name": "nllb", "state": "running", "pid": 999998, "started": 1792000000} #dead
[cosyvoice]
[batch_logs]
batch-kalel.log|1792000000|done: written 1332, skipped 0, failed 0 in 178.4m
[timers]
[end]
"""


def codes(findings):
    return {f.code for f in findings}


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


def test_etime_formats():
    assert parse_etime("05:09") == 309
    assert parse_etime("02:14:07") == 2 * 3600 + 14 * 60 + 7
    assert parse_etime("1-13:52:40") == 86400 + 13 * 3600 + 52 * 60 + 40


def test_parse_ps_line_keeps_full_args():
    p = parse_ps_line("nvidia 674839 672963 Sl+ 1-13:52:40 762 3644752 /usr/bin/python3 -m uvicorn x:app --port 8002")
    assert p.pid == 674839 and p.ppid == 672963 and p.pcpu == 762 and p.rss_kb == 3644752
    assert p.args.endswith("--port 8002")
    assert parse_ps_line("garbage") is None


def test_spark_runaway_gb10_na_memory_and_oom():
    rep = parse_report("spark", SPARK)
    assert rep.ok and rep.gpus[0]["mem_total_mib"] is None and rep.gpus[0]["util"] == 0
    found = analyze(rep, {"reserve_mem_gb": "16", "gpu_jobs": "1"})
    c = codes(found)
    assert {"HIGH_CPU_UNVERIFIED", "ZOMBIE", "LOAD_HIGH", "GPU_IDLE_CPU_BUSY", "GPU_MEM_SHARED", "COSYVOICE_INGEST"} <= c
    assert not ({"POSSIBLE_RUNAWAY", "BUSY_SERVING"} & c)  # no sample and no owner data: never a verdict
    hot = next(f for f in found if f.code == "HIGH_CPU_UNVERIFIED")
    assert hot.severity == WARN and "674839" in hot.message and "kill" not in hot.fix
    zombie = next(f for f in found if f.code == "ZOMBIE")
    assert "4242" in zombie.message and "kill -TERM 4242" in zombie.fix
    cv = next(f for f in found if f.code == "COSYVOICE_INGEST")
    assert cv.severity == WARN and "oom" in cv.message
    assert found == sorted(found, key=lambda f: {"crit": 0, "warn": 1, "info": 2}[f.severity])


def test_heavy_unmanaged_job_is_an_orphan_but_idle_helpers_are_not():
    rep = parse_report("spark", SPARK)
    assert "ORPHAN" in codes(analyze(rep))
    quiet = SPARK.replace("762", "0.0").replace("254", "0.0").replace("27856832", "5000")
    rep2 = parse_report("spark", quiet)
    assert "ORPHAN" not in codes(analyze(rep2))


def test_idle_kalel_with_stale_lock_and_dead_job_record():
    rep = parse_report("kalel", KALEL)
    found = analyze(rep, {"reserve_mem_gb": "6", "gpu_jobs": "1"})
    c = codes(found)
    assert {"STALE_LOCK", "JOB_RECORD_DEAD", "BATCH_LOG"} <= c
    assert not ({"POSSIBLE_RUNAWAY", "ZOMBIE", "MEM_LOW", "LOAD_HIGH", "GPU_CONTENTION"} & c)
    assert next(f for f in found if f.code == "STALE_LOCK").fix.endswith(".owner")


def test_memory_floor_and_gpu_contention():
    text = KALEL.replace("mem_avail_kb=26000000", "mem_avail_kb=2000000").replace("[procs_cpu]", "gpu_app=1|100\ngpu_app=2|100\n[procs_cpu]", 1)
    found = analyze(parse_report("kalel", text), {"reserve_mem_gb": "6", "gpu_jobs": "1"})
    low = next(f for f in found if f.code == "MEM_LOW")
    assert low.severity == CRIT  # 1.9 GB is under half the 6 GB reserve
    assert "GPU_CONTENTION" in codes(found)


def test_missing_nvidia_smi_means_no_gpu_findings():
    text = KALEL.replace("gpu=NVIDIA GeForce RTX 5060 Ti|2|1200|8151|45", "gpu=none")
    rep = parse_report("kalel", text)
    assert rep.gpus == []
    assert not any(c.startswith("GPU") for c in codes(analyze(rep)))


def test_unreachable_host_is_critical_with_ip_hint():
    rep = parse_report("kalel", "FLEET_UNREACHABLE ssh: connect to host 192.168.1.118 port 22: No route to host")
    found = analyze(rep)
    assert found[0].severity == CRIT and found[0].code == "UNREACHABLE"
    assert "FLEET_HOST_KALEL" in found[0].fix


def test_render_is_one_screen_and_never_runs_anything():
    reports = [parse_report("spark", SPARK), parse_report("kalel", KALEL)]
    text = render(reports, parse_budgets("[spark]\nreserve_mem_gb=16\n[kalel]\nreserve_mem_gb=6\n"))
    assert text.splitlines()[0].startswith("HOST")
    assert "WARN" in text and "HIGH_CPU_UNVERIFIED" in text and "kill 674839" not in text
    assert len(text.splitlines()) < 40


def test_budgets_parser_ignores_comments():
    b = parse_budgets("# top\n[spark]\nmatch=chans-spark|spark  # regex\nreserve_mem_gb=16\n\n[mac]\nreserve_cores=2\n")
    assert b["spark"]["match"] == "chans-spark|spark" and b["spark"]["reserve_mem_gb"] == "16" and b["mac"]["reserve_cores"] == "2"


def test_main_exit_codes_and_json(tmp_path, capsys):
    bad = tmp_path / "spark.report"
    bad.write_text(SPARK)
    good = tmp_path / "kalel.report"
    good.write_text(KALEL.replace("mem_avail_kb=26000000", "mem_avail_kb=26000000"))
    assert main(["render", f"spark={bad}"]) == 1  # unverified high CPU and a zombie are warnings, not critical
    capsys.readouterr()
    assert main(["render", f"down=" + str(_write(tmp_path, "down.report", "FLEET_UNREACHABLE no route"))]) == 2
    capsys.readouterr()
    assert main(["render", "--json", f"kalel={good}"]) == 1  # stale lock + dead record are warnings
    data = json.loads(capsys.readouterr().out)
    assert data[0]["host"] == "kalel" and any(f["code"] == "STALE_LOCK" for f in data[0]["findings"])


def test_real_probe_runs_here_and_parses():
    probe = REPO / "scripts" / "fleet" / "probe.sh"
    import os
    out = subprocess.run(["bash", str(probe)], capture_output=True, text=True, timeout=120,
                         env=dict(os.environ, FLEET_SAMPLE_SECONDS="1")).stdout
    rep = parse_report("here", out)
    assert rep.ok and rep.cpus > 0 and rep.mem_total_kb > 0 and rep.procs_cpu
    assert rep.owners, "the probe should describe the owners of the busiest processes"
    assert any(o.chain for o in rep.owners.values())
    assert not any(k not in ("NLLB_DEVICE", "CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES")
                   for o in rep.owners.values() for k in o.env), "only the allow-listed environment keys may appear"
    analyze(rep)  # must not raise


def test_module_cli_matches_script_entrypoint(tmp_path):
    rep = tmp_path / "spark.report"
    rep.write_text(SPARK)
    r = subprocess.run([sys.executable, "-m", "aoep_shared.fleet_status", "render", f"spark={rep}"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 1 and "HIGH_CPU_UNVERIFIED" in r.stdout


def _fake_ssh(tmp_path, ok_hosts):
    """A stand-in for ssh: logs its target, then 'connects' only to hosts in ok_hosts by running the probe locally."""
    log = tmp_path / "ssh.log"
    shim = tmp_path / "bin" / "ssh"
    shim.parent.mkdir()
    shim.write_text(
        "#!/bin/bash\n"
        'target=""\n'
        'for a in "$@"; do case "$a" in *@*) target="${a#*@}" ;; esac; done\n'
        f'echo "$target" >> {log}\n'
        f'case " {" ".join(ok_hosts)} " in *" $target "*) exec bash -s ;; esac\n'
        'echo "ssh: connect to host $target port 22: No route to host" >&2\n'
        "exit 255\n")
    shim.chmod(0o755)
    return shim.parent, log


def _fleet(tmp_path, hosts_text, path_dir, extra_env=None, args=()):
    import os
    hosts = tmp_path / "hosts.conf"
    hosts.write_text(hosts_text)
    env = dict(os.environ, FLEET_HOSTS_FILE=str(hosts), PATH=f"{path_dir}:{os.environ['PATH']}",
               FLEET_SAMPLE_SECONDS="0", **(extra_env or {}))
    return subprocess.run(["bash", str(REPO / "scripts" / "fleet_status.sh"), *args], capture_output=True, text=True,
                          env=env, cwd=str(REPO), timeout=120)


def test_fleet_status_falls_back_to_the_mdns_name_when_the_ip_moved(tmp_path):
    bin_dir, log = _fake_ssh(tmp_path, ["kal-el.local"])
    r = _fleet(tmp_path, "kalel cvanthin 192.168.1.118 Kal-el.local,kal-el.local\n", bin_dir)
    # The exit code depends on this machine's live memory, so only the routing is asserted.
    assert "UNREACHABLE" not in r.stdout and r.stdout.splitlines()[0].startswith("HOST"), r.stdout + r.stderr
    tried = log.read_text().split()
    assert tried[0] == "192.168.1.118" and tried[-1] == "kal-el.local"


def test_fleet_status_env_override_is_tried_first(tmp_path):
    bin_dir, log = _fake_ssh(tmp_path, ["192.168.1.119"])
    r = _fleet(tmp_path, "kalel cvanthin 192.168.1.118\n", bin_dir, {"FLEET_HOST_KALEL": "192.168.1.119"})
    assert "UNREACHABLE" not in r.stdout and log.read_text().split()[0] == "192.168.1.119"


def test_fleet_status_reports_unreachable_host_and_exits_2(tmp_path):
    bin_dir, _ = _fake_ssh(tmp_path, [])
    r = _fleet(tmp_path, "spark nvidia 192.168.1.107 Chans-Spark.local\n", bin_dir)
    assert r.returncode == 2
    assert "UNREACHABLE" in r.stdout and "FLEET_HOST_SPARK" in r.stdout


# ---- owner attribution and working-versus-spinning ----------------------------------------
# Modeled on the real Spark incident: the 'runaway' uvicorn was a legitimate NLLB translation gateway
# (NLLB_DEVICE=cpu) in tmux session nllb-speech, run from the worktree gs-wt/spark-eval-gates, with
# clients connected on port 8002.

OWNED = """[owners]
pid=674839
cwd=/home/nvidia/code/gs-wt/spark-eval-gates
git=/home/nvidia/code/gs-wt/spark-eval-gates|1|feat/spark-eval-gates|a1b2c3d|Add eval gates | for the nightly
cgroup=0::/user.slice/user-1000.slice/user@1000.service/tmux-spawn-abc.scope
chain=674839:python3 672963:bash 672500:tmux:_server
env=readable|NLLB_DEVICE=cpu
log=/home/nvidia/gs/logs/nllb-speech.log|1792826990
pid=3068016
cwd=/home/nvidia/code/getschoolled
git=/home/nvidia/code/getschoolled|0|main|7c7f483|Back off voice training
chain=3068016:python3
env=readable|
[tmux]
672963 nllb-speech main
672990 nllb-gateway main
673010 course-translate main
[sockets]
LISTEN 0 2048 127.0.0.1:8002 0.0.0.0:* users:(("uvicorn",pid=674839,fd=12))
ESTAB 0 0 127.0.0.1:8002 127.0.0.1:51234 users:(("uvicorn",pid=674839,fd=20))
ESTAB 0 0 127.0.0.1:8002 127.0.0.1:51236 users:(("uvicorn",pid=674839,fd=21))
ESTAB 0 0 127.0.0.1:51234 127.0.0.1:8002 users:(("python3",pid=700001,fd=5))
[sample]
interval=10
clk_tck=100
t0 674839 100000 5000000
t1 674839 107600 5400000
"""
NO_CLIENTS = OWNED.replace("ESTAB", "TIMEWAIT")  # parse_ss_line only keeps LISTEN and ESTAB rows
OLD_LOG = "|1792826990", "|1792000000"
SAME_IO = "t1 674839 107600 5400000", "t1 674839 107600 5000000"


def owned_report(extra=OWNED, base=SPARK):
    return base.replace("[end]\n", extra + "[end]\n")


def finding(found, code):
    return next(f for f in found if f.code == code)


def test_busy_server_with_clients_is_busy_serving_not_a_kill_suggestion():
    found = analyze(parse_report("spark", owned_report()), {"reserve_mem_gb": "16"})
    assert "BUSY_SERVING" in codes(found) and not ({"POSSIBLE_RUNAWAY", "HIGH_CPU_UNVERIFIED"} & codes(found))
    f = finding(found, "BUSY_SERVING")
    assert f.severity == "info" and f.fix == ""
    assert "serving 2 client(s) on port 8002" in f.message and "Not a kill suggestion" in f.message
    assert "tmux 'nllb-speech' window 'main'" in f.message
    assert "worktree spark-eval-gates (feat/spark-eval-gates @ a1b2c3d" in f.message
    assert "last log write 10 s ago" in f.message and "tmux-spawn-abc.scope" in f.message


def test_every_top_process_shows_owner_chain_port_and_environment():
    top = finding(analyze(parse_report("spark", owned_report())), "TOP_PROC")
    assert "pid 674839" in top.message and "listens on 8002, serving 2 client(s)" in top.message
    assert "chain: 674839:python3 < 672963:bash < 672500:tmux:_server" in top.message
    assert "NLLB_DEVICE=cpu" in top.message and "CUDA_VISIBLE_DEVICES=(unset)" in top.message


def test_commit_subject_with_a_pipe_survives_parsing():
    rep = parse_report("spark", owned_report())
    owner = rep.owners[674839]
    assert owner.commit == "a1b2c3d" and owner.subject == "Add eval gates | for the nightly" and owner.worktree
    assert owner.unit == "tmux-spawn-abc.scope"
    assert rep.owners[3068016].worktree is False


def test_high_cpu_with_no_clients_no_io_and_old_log_is_a_possible_runaway():
    spinning = NO_CLIENTS.replace(*SAME_IO).replace(*OLD_LOG)
    found = analyze(parse_report("spark", owned_report(spinning)))
    f = finding(found, "POSSIBLE_RUNAWAY")
    assert f.severity == "warn" and "760% CPU over 10 s, no clients, no IO growth" in f.message
    assert "listening on 8002 with nobody connected" in f.message
    assert "ask the owner first" in f.fix and "--i-know-owner" in f.fix  # tmux/worktree owned: needs the override
    assert "BUSY_SERVING" not in codes(found)


def test_unowned_possible_runaway_fix_does_not_need_the_override():
    spinning = (NO_CLIENTS.replace(*SAME_IO).replace(*OLD_LOG).replace("672963 nllb-speech main", "1 other main")
                .replace("|1|feat/spark-eval-gates", "|0|feat/spark-eval-gates"))
    f = finding(analyze(parse_report("spark", owned_report(spinning))), "POSSIBLE_RUNAWAY")
    assert "--i-know-owner" not in f.fix and f.fix.rstrip().endswith("--yes")


def test_log_writes_or_io_alone_also_count_as_working():
    by_log = analyze(parse_report("spark", owned_report(NO_CLIENTS.replace(*SAME_IO))))
    assert "BUSY_SERVING" in codes(by_log) and "last log write" in finding(by_log, "BUSY_SERVING").message
    by_io = analyze(parse_report("spark", owned_report(NO_CLIENTS.replace(*OLD_LOG))))
    assert "BUSY_SERVING" in codes(by_io) and "KB read/written" in finding(by_io, "BUSY_SERVING").message


def test_without_a_sample_or_io_counters_it_is_unverified_never_runaway():
    quiet = NO_CLIENTS.replace(*OLD_LOG)
    no_sample = owned_report(quiet.split("[sample]")[0])
    f = finding(analyze(parse_report("spark", no_sample)), "HIGH_CPU_UNVERIFIED")
    assert "no CPU/IO sample" in f.message and "fleet_reap" not in f.fix
    unreadable = owned_report(quiet.replace("5000000", "na").replace("5400000", "na"))
    f2 = finding(analyze(parse_report("spark", unreadable)), "HIGH_CPU_UNVERIFIED")
    assert "IO counters are unreadable" in f2.message
    calmed = owned_report(quiet.replace(*SAME_IO).replace("107600", "100200"))
    f3 = finding(analyze(parse_report("spark", calmed)), "HIGH_CPU_UNVERIFIED")
    assert "calmed down" in f3.message


def test_gpu_idle_while_cpu_bound_shows_the_device_settings():
    f = finding(analyze(parse_report("spark", owned_report())), "GPU_IDLE_CPU_BUSY")
    assert f.severity == "warn"
    assert "GPU 0% while 12 cores busy: check NLLB_DEVICE/CUDA device settings in the process environment" in f.message
    assert "pid 674839: NLLB_DEVICE=cpu CUDA_VISIBLE_DEVICES=(unset)" in f.message
    assert "environment not probed" in finding(analyze(parse_report("spark", SPARK)), "GPU_IDLE_CPU_BUSY").message
    idle = SPARK.replace("762", "10").replace("254", "10").replace("149", "10")
    assert "GPU_IDLE_CPU_BUSY" not in codes(analyze(parse_report("spark", idle)))


def test_unreadable_environment_is_reported_as_such():
    text = owned_report(OWNED.replace("env=readable|NLLB_DEVICE=cpu\n", "env=unreadable|\n"))
    assert "environment unreadable (other user)" in finding(analyze(parse_report("spark", text)), "GPU_IDLE_CPU_BUSY").message


def test_gs_run_started_jobs_are_labelled():
    jobs = '[jobs]\n{"id": "j1", "name": "nllb", "state": "running", "pid": 674000, "child_pid": 674839} #alive\n'
    text = owned_report(OWNED).replace("[jobs]\n", jobs, 1)
    assert "started via gs_run" in finding(analyze(parse_report("spark", text)), "BUSY_SERVING").message


def test_zombie_whose_parent_is_in_someone_elses_tmux_is_not_a_kill_suggestion():
    text = owned_report(OWNED).replace("nvidia 538549 4242 Z", "nvidia 538549 674839 Z")
    f = finding(analyze(parse_report("spark", text)), "ZOMBIE")
    assert "someone else's session" in f.fix and "kill -TERM" not in f.fix and "--i-know-owner" in f.fix


def test_orphan_in_a_worktree_or_tmux_is_left_alone():
    text = owned_report(OWNED).replace("[orphans]\nnvidia 3068016 1", "[orphans]\nnvidia 674839 1")
    f = finding(analyze(parse_report("spark", text)), "ORPHAN")
    assert "leave it, or ask the owner" in f.fix and "tmux 'nllb-speech'" in f.message


def test_ss_line_variants():
    from aoep_shared.fleet_status import parse_ss_line
    v6 = parse_ss_line('LISTEN 0 4096 [::]:8080 [::]:* users:(("llama-server",pid=5186,fd=3))')
    assert v6.local_port == 8080 and v6.pids == [5186] and v6.state == "LISTEN"
    plain = parse_ss_line("ESTAB 0 0 10.0.0.5:22 10.0.0.9:50000")
    assert plain.local_port == 22 and plain.pids == []
    assert parse_ss_line("TIME-WAIT 0 0 1.2.3.4:1 5.6.7.8:2") is None
    assert parse_ss_line("junk") is None
