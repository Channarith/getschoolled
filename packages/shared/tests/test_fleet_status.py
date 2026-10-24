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
    assert {"RUNAWAY", "ZOMBIE", "LOAD_HIGH", "GPU_IDLE_CPU_BUSY", "GPU_MEM_SHARED", "COSYVOICE_INGEST"} <= c
    runaway = next(f for f in found if f.code == "RUNAWAY")
    assert runaway.severity == CRIT and "674839" in runaway.message and runaway.fix.startswith("kill 674839")
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
    assert not ({"RUNAWAY", "ZOMBIE", "MEM_LOW", "LOAD_HIGH", "GPU_CONTENTION"} & c)
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
    assert "CRIT" in text and "fix: kill 674839" in text
    assert len(text.splitlines()) < 40


def test_budgets_parser_ignores_comments():
    b = parse_budgets("# top\n[spark]\nmatch=chans-spark|spark  # regex\nreserve_mem_gb=16\n\n[mac]\nreserve_cores=2\n")
    assert b["spark"]["match"] == "chans-spark|spark" and b["spark"]["reserve_mem_gb"] == "16" and b["mac"]["reserve_cores"] == "2"


def test_main_exit_codes_and_json(tmp_path, capsys):
    bad = tmp_path / "spark.report"
    bad.write_text(SPARK)
    good = tmp_path / "kalel.report"
    good.write_text(KALEL.replace("mem_avail_kb=26000000", "mem_avail_kb=26000000"))
    assert main(["render", f"spark={bad}"]) == 2
    capsys.readouterr()
    assert main(["render", "--json", f"kalel={good}"]) == 1  # stale lock + dead record are warnings
    data = json.loads(capsys.readouterr().out)
    assert data[0]["host"] == "kalel" and any(f["code"] == "STALE_LOCK" for f in data[0]["findings"])


def test_real_probe_runs_here_and_parses():
    probe = REPO / "scripts" / "fleet" / "probe.sh"
    out = subprocess.run(["bash", str(probe)], capture_output=True, text=True, timeout=60).stdout
    rep = parse_report("here", out)
    assert rep.ok and rep.cpus > 0 and rep.mem_total_kb > 0 and rep.procs_cpu
    analyze(rep)  # must not raise


def test_module_cli_matches_script_entrypoint(tmp_path):
    rep = tmp_path / "spark.report"
    rep.write_text(SPARK)
    r = subprocess.run([sys.executable, "-m", "aoep_shared.fleet_status", "render", f"spark={rep}"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 2 and "RUNAWAY" in r.stdout


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
    env = dict(os.environ, FLEET_HOSTS_FILE=str(hosts), PATH=f"{path_dir}:{os.environ['PATH']}", **(extra_env or {}))
    return subprocess.run(["bash", str(REPO / "scripts" / "fleet_status.sh"), *args], capture_output=True, text=True,
                          env=env, cwd=str(REPO), timeout=120)


def test_fleet_status_falls_back_to_the_mdns_name_when_the_ip_moved(tmp_path):
    bin_dir, log = _fake_ssh(tmp_path, ["kal-el.local"])
    r = _fleet(tmp_path, "kalel cvanthin 192.168.1.118 Kal-el.local,kal-el.local\n", bin_dir)
    assert r.returncode in (0, 1), r.stdout + r.stderr
    assert "UNREACHABLE" not in r.stdout and r.stdout.splitlines()[0].startswith("HOST")
    tried = log.read_text().split()
    assert tried[0] == "192.168.1.118" and tried[-1] == "kal-el.local"


def test_fleet_status_env_override_is_tried_first(tmp_path):
    bin_dir, log = _fake_ssh(tmp_path, ["192.168.1.119"])
    r = _fleet(tmp_path, "kalel cvanthin 192.168.1.118\n", bin_dir, {"FLEET_HOST_KALEL": "192.168.1.119"})
    assert r.returncode in (0, 1) and log.read_text().split()[0] == "192.168.1.119"


def test_fleet_status_reports_unreachable_host_and_exits_2(tmp_path):
    bin_dir, _ = _fake_ssh(tmp_path, [])
    r = _fleet(tmp_path, "spark nvidia 192.168.1.107 Chans-Spark.local\n", bin_dir)
    assert r.returncode == 2
    assert "UNREACHABLE" in r.stdout and "FLEET_HOST_SPARK" in r.stdout
