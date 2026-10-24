#!/usr/bin/env python3
"""Read-only machine inventory as JSON, for scripts/fleet/work_split.py.

  python3 scripts/fleet/inventory.py [--name spark|kalel|mac] [--out inv.json]
  ssh host 'python3 -' < scripts/fleet/inventory.py        (work_split.py gather does this)

Reports hostname, OS, GPU, CUDA (does torch see it), memory, disk, python and whether the GPU lock is held.
It changes nothing: no files except --out, no processes, no network. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time

TORCH_PROBE = "import torch,json;print(json.dumps({'cuda':bool(torch.cuda.is_available()),'torch':torch.__version__,'mps':bool(getattr(torch.backends,'mps',None) and torch.backends.mps.is_available())}))"


def _run(cmd, timeout=20):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def memory_gb() -> tuple[float, float]:
    """(total, available) in GB. Available is what a new job can really use (MemAvailable / free+inactive pages)."""
    if platform.system() == "Darwin":
        total = int(_run(["sysctl", "-n", "hw.memsize"]) or 0)
        vm = _run(["vm_stat"])
        page = int((re.search(r"page size of (\d+)", vm) or [0, 4096])[1])
        pages = sum(int(m) for m in re.findall(r"Pages (?:free|inactive|speculative):\s+(\d+)", vm))
        return round(total / 2**30, 1), round(pages * page / 2**30, 1)
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                info[k] = int(v.split()[0])
    except OSError:
        return 0.0, 0.0
    return round(info.get("MemTotal", 0) / 2**20, 1), round(info.get("MemAvailable", 0) / 2**20, 1)


def gpu() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"name": None, "mem_total_gb": None}
    row = _run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"]).splitlines()
    if not row:
        return {"name": None, "mem_total_gb": None}
    name, total, used = [x.strip() for x in row[0].split(",")][:3]
    # The Spark has unified memory: nvidia-smi reports [N/A]; the shared pool is the system memory.
    try:
        return {"name": name, "mem_total_gb": round(float(total) / 1024, 1), "mem_used_gb": round(float(used) / 1024, 1)}
    except ValueError:
        return {"name": name, "mem_total_gb": None, "unified_memory": True}


def torch_info() -> dict:
    for py in (os.environ.get("GS_PYTHON"), os.path.expanduser("~/code/getschoolled/.venv/bin/python"), sys.executable):
        if py and os.path.exists(py):
            out = _run([py, "-c", TORCH_PROBE], timeout=60)
            if out.startswith("{"):
                return {**json.loads(out), "python": py}
    return {"cuda": False, "torch": None, "mps": False, "python": sys.executable}


def lock_held(path: str) -> bool:
    """True if another process holds the GPU lock (non-blocking flock probe; releases at once)."""
    try:
        import fcntl
        with open(path, "a") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(f, fcntl.LOCK_UN)
    except (OSError, ImportError):
        return False
    return False


def collect(name: str | None = None) -> dict:
    total, avail = memory_gb()
    g = gpu()
    t = torch_info()
    disk = shutil.disk_usage(os.path.expanduser("~"))
    return {
        "schema": 1,
        "name": name or "",
        "hostname": socket.gethostname().split(".")[0],
        "os": platform.system(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "cpus": os.cpu_count() or 0,
        "mem_total_gb": total,
        "mem_avail_gb": avail,
        "disk_free_gb": round(disk.free / 2**30, 1),
        "gpu": g,
        "cuda": bool(t["cuda"]),
        "mps": bool(t["mps"]),
        "torch": t["torch"],
        "gpu_lock_held": lock_held(os.path.expanduser("~/.gs-gpu.lock")),
        "collected": int(time.time()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="", help="fleet name to record (spark|kalel|mac)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    text = json.dumps(collect(args.name), indent=1)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
