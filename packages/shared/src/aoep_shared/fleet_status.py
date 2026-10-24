"""Parse scripts/fleet/probe.sh reports and turn them into findings.

Pure functions: no SSH, no subprocess. scripts/fleet_status.sh collects the reports and calls
`python3 -m aoep_shared.fleet_status render ...`. Nothing here ever changes a machine; remediation
commands are only suggested as text.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CRIT, WARN, INFO = "crit", "warn", "info"
_ORDER = {CRIT: 0, WARN: 1, INFO: 2}

RUNAWAY_CPU_PCT = 300.0
RUNAWAY_MIN_SECONDS = 30 * 60
ORPHAN_MIN_SECONDS = 60 * 60
ORPHAN_MIN_CPU_PCT = 5.0
ORPHAN_MIN_RSS_KB = 500 * 1024
DEFAULT_RESERVE_GB = 4.0


@dataclass
class Proc:
    user: str
    pid: int
    ppid: int
    stat: str
    etime_s: int
    pcpu: float
    rss_kb: int
    args: str


@dataclass
class Finding:
    severity: str
    host: str
    code: str
    message: str
    fix: str = ""


@dataclass
class HostReport:
    name: str
    ok: bool = True
    error: str = ""
    host: str = ""
    os: str = ""
    cpus: int = 0
    load: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mem_total_kb: int = 0
    mem_avail_kb: int = 0
    swap_used_kb: int = 0
    disk_pct: int | None = None
    gpus: list[dict[str, Any]] = field(default_factory=list)
    gpu_apps: list[tuple[int, int | None]] = field(default_factory=list)
    procs_cpu: list[Proc] = field(default_factory=list)
    procs_rss: list[Proc] = field(default_factory=list)
    zombies: list[Proc] = field(default_factory=list)
    zombie_parents: dict[int, Proc] = field(default_factory=dict)
    orphans: list[Proc] = field(default_factory=list)
    lock: dict[str, str] = field(default_factory=dict)
    jobs: list[dict[str, Any]] = field(default_factory=list)
    cosyvoice: dict[str, Any] = field(default_factory=dict)
    batch_logs: list[dict[str, Any]] = field(default_factory=list)
    timers: list[str] = field(default_factory=list)
    now: int = 0


def parse_etime(text: str) -> int:
    """ps etime: [[dd-]hh:]mm:ss -> seconds."""
    text = text.strip()
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        days = int(d)
    parts = [int(p) for p in text.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return days * 86400 + h * 3600 + m * 60 + s


def parse_ps_line(line: str) -> Proc | None:
    parts = line.split(None, 7)
    if len(parts) < 7:
        return None
    try:
        return Proc(
            user=parts[0],
            pid=int(parts[1]),
            ppid=int(parts[2]),
            stat=parts[3],
            etime_s=parse_etime(parts[4]),
            pcpu=float(parts[5]),
            rss_kb=int(parts[6]),
            args=parts[7].strip() if len(parts) > 7 else "",
        )
    except ValueError:
        return None


def _num(text: str | None) -> float | None:
    if text is None:
        return None
    text = text.strip()
    if not text or text.upper() in ("N/A", "[N/A]", "NA", "[NOT SUPPORTED]"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_gpu(value: str) -> dict[str, Any] | None:
    if value.strip() == "none":
        return None
    parts = (value.split("|") + [""] * 5)[:5]
    return {
        "name": parts[0].strip(),
        "util": _num(parts[1]),
        "mem_used_mib": _num(parts[2]),
        "mem_total_mib": _num(parts[3]),
        "temp_c": _num(parts[4]),
    }


def parse_report(name: str, text: str) -> HostReport:
    """Parse one probe report. A report starting with FLEET_UNREACHABLE marks the host down."""
    rep = HostReport(name=name)
    lines = text.splitlines()
    if not lines or lines[0].startswith("FLEET_UNREACHABLE") or not lines[0].startswith("FLEET_PROBE"):
        rep.ok = False
        rep.error = (lines[0].partition(" ")[2] if lines else "") or "no report"
        return rep
    section = ""
    for raw in lines[1:]:
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if not section:
            key, _, value = line.partition("=")
            if key == "host":
                rep.host = value
            elif key == "os":
                rep.os = value
            elif key == "now":
                rep.now = int(_num(value) or 0)
            elif key == "cpus":
                rep.cpus = int(_num(value) or 0)
            elif key == "load":
                nums = [_num(p) or 0.0 for p in value.split()[:3]]
                rep.load = tuple((nums + [0.0, 0.0, 0.0])[:3])  # type: ignore[assignment]
            elif key in ("mem_total_kb", "mem_avail_kb", "swap_used_kb"):
                setattr(rep, key, int(_num(value) or 0))
            elif key == "disk":
                f = value.split()
                if len(f) >= 5:
                    rep.disk_pct = int(_num(f[4]) or 0)
            elif key == "gpu":
                gpu = _parse_gpu(value)
                if gpu:
                    rep.gpus.append(gpu)
            elif key == "gpu_app":
                pid, _, mem = value.partition("|")
                rep.gpu_apps.append((int(_num(pid) or 0), int(_num(mem)) if _num(mem) is not None else None))
            continue
        if section in ("procs_cpu", "procs_rss", "zombies", "zombie_parents", "orphans"):
            proc = parse_ps_line(line)
            if proc is None:
                continue
            if section == "zombie_parents":
                rep.zombie_parents[proc.pid] = proc
            else:
                getattr(rep, section).append(proc)
        elif section == "lock":
            key, _, value = line.partition("=")
            rep.lock[key] = value
        elif section == "jobs":
            rep.jobs.append(_parse_job(line))
        elif section == "cosyvoice":
            if line.startswith("mtime="):
                rep.cosyvoice["_mtime"] = int(_num(line[6:]) or 0)
            elif line.startswith("{"):
                try:
                    rep.cosyvoice.update(json.loads(line))
                except json.JSONDecodeError:
                    rep.cosyvoice["_bad_json"] = True
        elif section == "batch_logs":
            fname, _, rest = line.partition("|")
            mtime, _, last = rest.partition("|")
            rep.batch_logs.append({"file": fname, "mtime": int(_num(mtime) or 0), "last": last})
        elif section == "timers":
            rep.timers.append(line.strip())
    return rep


def _parse_job(line: str) -> dict[str, Any]:
    alive = line.rstrip().endswith("#alive")
    body = re.sub(r"\s*#(alive|dead)\s*$", "", line)
    try:
        rec = json.loads(body)
    except json.JSONDecodeError:
        rec = {"raw": body[:200]}
    rec["_alive"] = alive
    return rec


def parse_budgets(text: str) -> dict[str, dict[str, str]]:
    """Tiny INI reader for scripts/fleet/budgets.conf: [section] then key=value."""
    out: dict[str, dict[str, str]] = {}
    section = ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            out.setdefault(section, {})
        elif "=" in line and section:
            k, _, v = line.partition("=")
            out[section][k.strip()] = v.strip()
    return out


def _gb(kb: int) -> float:
    return kb / 1048576.0


def analyze(rep: HostReport, budget: dict[str, str] | None = None) -> list[Finding]:
    """Findings for one host, most severe first. fix is a suggestion only."""
    budget = budget or {}
    name = rep.name
    if not rep.ok:
        return [Finding(CRIT, name, "UNREACHABLE", f"cannot reach {name}: {rep.error}",
                        f"ssh -o BatchMode=yes <user>@<ip> true   (IP may have changed; set FLEET_HOST_{name.upper().replace('-', '_')}=<ip>)")]
    out: list[Finding] = []
    reserve_gb = float(budget.get("reserve_mem_gb", DEFAULT_RESERVE_GB))
    avail_gb = _gb(rep.mem_avail_kb)

    if rep.mem_total_kb and avail_gb < reserve_gb:
        sev = CRIT if avail_gb < reserve_gb / 2 else WARN
        top = rep.procs_rss[0] if rep.procs_rss else None
        hint = f"largest process: pid {top.pid} ({top.rss_kb // 1048576} GB) {top.args[:60]}" if top else ""
        out.append(Finding(sev, name, "MEM_LOW",
                           f"{avail_gb:.1f} GB available, below the {reserve_gb:g} GB reserve. {hint}".strip(),
                           "scripts/fleet_reap.sh   (lists what is safe to stop); start new jobs through scripts/gs_run.sh"))
    if rep.swap_used_kb > 4 * 1048576:
        out.append(Finding(WARN, name, "SWAP_HEAVY", f"{_gb(rep.swap_used_kb):.1f} GB of swap in use", ""))

    load1 = rep.load[0]
    if rep.cpus and load1 > rep.cpus * 3:
        out.append(Finding(CRIT, name, "LOAD_HIGH", f"load {load1:.1f} on {rep.cpus} cores (over 3x)", ""))
    elif rep.cpus and load1 > rep.cpus * 1.5:
        out.append(Finding(WARN, name, "LOAD_HIGH", f"load {load1:.1f} on {rep.cpus} cores (over 1.5x)", ""))

    seen: set[int] = set()
    for p in rep.procs_cpu:
        if p.pcpu > RUNAWAY_CPU_PCT and p.etime_s > RUNAWAY_MIN_SECONDS and p.pid not in seen:
            seen.add(p.pid)
            hours = p.etime_s / 3600
            out.append(Finding(CRIT, name, "RUNAWAY",
                               f"pid {p.pid} at {p.pcpu:.0f}% CPU for {hours:.1f} h: {p.args[:90]}",
                               f"kill {p.pid}   (check first: ps -o pid,ppid,etime,args -p {p.pid})"))

    for z in rep.zombies:
        parent = rep.zombie_parents.get(z.ppid)
        pdesc = f"parent pid {z.ppid} {parent.args[:70]}" if parent else f"parent pid {z.ppid}"
        fix = ("the parent is init, which reaps it; if it stays, reboot" if z.ppid == 1
               else f"kill -TERM {z.ppid}   (a zombie cannot be killed; its parent must exit or reap it)")
        out.append(Finding(WARN, name, "ZOMBIE", f"defunct pid {z.pid} ({z.args[:40]}), {pdesc}", fix))

    for o in rep.orphans:
        heavy = o.pcpu >= ORPHAN_MIN_CPU_PCT or o.rss_kb >= ORPHAN_MIN_RSS_KB
        if o.etime_s >= ORPHAN_MIN_SECONDS and heavy:
            out.append(Finding(WARN, name, "ORPHAN",
                               f"pid {o.pid} (user {o.user}, parent 1) running {o.etime_s / 3600:.1f} h at {o.pcpu:.0f}% CPU, "
                               f"{o.rss_kb // 1048576} GB: {o.args[:70]}",
                               "unmanaged job: start it through scripts/gs_run.sh next time; stop with kill <pid> if unneeded"))

    for i, g in enumerate(rep.gpus):
        util = g.get("util")
        if util is not None and util < 5 and rep.cpus and load1 > rep.cpus:
            out.append(Finding(INFO, name, "GPU_IDLE_CPU_BUSY",
                               f"GPU {g['name']} at {util:.0f}% while the CPU is saturated: the busy jobs are probably CPU-bound",
                               "check that heavy jobs use cuda (torch.cuda.is_available(), --device cuda)"))
        if g.get("mem_total_mib") is None and i == 0:
            out.append(Finding(INFO, name, "GPU_MEM_SHARED", "GPU memory is not reported (unified memory); watch system memory instead", ""))
    max_gpu_jobs = int(budget.get("gpu_jobs", "1") or 1)
    if len(rep.gpu_apps) > max_gpu_jobs:
        pids = ", ".join(str(p) for p, _ in rep.gpu_apps)
        out.append(Finding(WARN, name, "GPU_CONTENTION",
                           f"{len(rep.gpu_apps)} processes on the GPU (budget {max_gpu_jobs}): {pids}",
                           "run GPU jobs one at a time: scripts/gs_run.sh --gpu -- <cmd>"))

    lock = rep.lock
    if lock.get("owner") and lock.get("owner_alive") == "no" and not lock.get("holders", "").strip():
        out.append(Finding(WARN, name, "STALE_LOCK", f"GPU lock owner record is dead: {lock['owner'][:80]}",
                           f"rm {lock.get('path', '~/.gs-gpu.lock')}.owner"))
    holders = lock.get("holders", "").split()
    if len(holders) > 1:
        out.append(Finding(WARN, name, "LOCK_SHARED", f"several processes hold the GPU lock file: {' '.join(holders)}",
                           "only gs_run.sh and training/spark_nightly.sh should hold it"))

    if rep.disk_pct is not None:
        if rep.disk_pct >= 95:
            out.append(Finding(CRIT, name, "DISK_FULL", f"root disk {rep.disk_pct}% used", "du -sh ~/.cache/* output/* | sort -h | tail"))
        elif rep.disk_pct >= 90:
            out.append(Finding(WARN, name, "DISK_HIGH", f"root disk {rep.disk_pct}% used", "du -sh ~/.cache/* output/* | sort -h | tail"))

    for job in rep.jobs:
        if job.get("state") == "running" and not job.get("_alive"):
            out.append(Finding(WARN, name, "JOB_RECORD_DEAD",
                               f"job {job.get('id', '?')} ({job.get('name', '')}) is recorded as running but pid {job.get('pid')} is gone",
                               "scripts/fleet_reap.sh --yes   (marks the record finished)"))
        elif job.get("state") == "running":
            out.append(Finding(INFO, name, "JOB", f"job {job.get('id', '?')} {job.get('name', '')} pid {job.get('pid')} running", ""))

    cv = rep.cosyvoice
    if cv and not cv.get("_bad_json"):
        age_h = (rep.now - cv.get("_mtime", rep.now)) / 3600 if rep.now else 0
        line = (f"CosyVoice ingest: phase={cv.get('phase')} done={cv.get('done')}/{cv.get('queued')} "
                f"failed={cv.get('failed')} running={cv.get('running')} (status {age_h:.1f} h old)")
        sev = WARN if cv.get("last_error") == "oom" else INFO
        if cv.get("last_error"):
            line += f" last_error={cv['last_error']}"
        out.append(Finding(sev, name, "COSYVOICE_INGEST", line,
                           "lower AOEP_INGEST_WORKER_MB pressure: run via scripts/gs_run.sh with a memory cap" if sev == WARN else ""))
    for b in rep.batch_logs:
        age_h = (rep.now - b["mtime"]) / 3600 if rep.now and b["mtime"] else 0
        finished = b["last"].lower().startswith("done")
        out.append(Finding(INFO, name, "BATCH_LOG",
                           f"{b['file']}: {'finished' if finished else 'last line'} {age_h:.0f} h ago: {b['last'][:90]}", ""))
    if rep.timers:
        out.append(Finding(INFO, name, "TIMERS", f"{len(rep.timers)} relevant systemd user timer(s)", ""))
    out.sort(key=lambda f: _ORDER[f.severity])
    return out


def _mem_cell(rep: HostReport) -> str:
    return f"{_gb(rep.mem_avail_kb):.0f}/{_gb(rep.mem_total_kb):.0f} GB" if rep.mem_total_kb else "-"


def _gpu_cell(rep: HostReport) -> str:
    if not rep.gpus:
        return "none"
    g = rep.gpus[0]
    util = f"{g['util']:.0f}%" if g.get("util") is not None else "?"
    mem = ""
    if g.get("mem_total_mib") is not None and g.get("mem_used_mib") is not None:
        mem = f" {g['mem_used_mib'] / 1024:.1f}/{g['mem_total_mib'] / 1024:.0f}G"
    return f"{util}{mem} jobs={len(rep.gpu_apps)}"


def render(reports: list[HostReport], budgets: dict[str, dict[str, str]] | None = None) -> str:
    budgets = budgets or {}
    rows = []
    all_findings: list[Finding] = []
    for rep in reports:
        findings = analyze(rep, budgets.get(rep.name))
        all_findings.extend(findings)
        worst = min((_ORDER[f.severity] for f in findings if f.severity != INFO), default=3)
        status = {0: "CRIT", 1: "WARN", 3: "OK"}.get(worst, "OK")
        if not rep.ok:
            rows.append((rep.name, status, "-", "-", "-", rep.error[:40]))
        else:
            rows.append((rep.name, status, f"{rep.load[0]:.1f}/{rep.cpus}", _mem_cell(rep), _gpu_cell(rep),
                         f"{sum(f.severity != INFO for f in findings)} issue(s)"))
    head = ("HOST", "STATUS", "LOAD/CPUS", "MEM AVAIL", "GPU", "NOTES")
    widths = [max(len(str(r[i])) for r in [head] + rows) for i in range(len(head))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    lines = [fmt.format(*head)] + [fmt.format(*[str(c) for c in r]) for r in rows]
    if all_findings:
        lines.append("")
        for f in all_findings:
            tag = {CRIT: "CRIT", WARN: "WARN", INFO: "info"}[f.severity]
            lines.append(f"[{tag}] {f.host}/{f.code}: {f.message}")
            if f.fix:
                lines.append(f"       fix: {f.fix}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """render --budgets FILE [--json] name=reportfile ...   Exit 2 if any CRIT, 1 if any WARN."""
    budgets: dict[str, dict[str, str]] = {}
    as_json = False
    reports: list[HostReport] = []
    args = list(argv)
    if args and args[0] == "render":
        args = args[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--budgets":
            budgets = parse_budgets(Path(args[i + 1]).read_text())
            i += 2
        elif a == "--json":
            as_json = True
            i += 1
        elif "=" in a:
            name, _, path = a.partition("=")
            reports.append(parse_report(name, Path(path).read_text(errors="replace")))
            i += 1
        else:
            i += 1
    if as_json:
        print(json.dumps([{"host": r.name, "ok": r.ok, "error": r.error,
                           "findings": [f.__dict__ for f in analyze(r, budgets.get(r.name))]} for r in reports], indent=2))
    else:
        print(render(reports, budgets))
    sev = [f.severity for r in reports for f in analyze(r, budgets.get(r.name))]
    return 2 if CRIT in sev else 1 if WARN in sev else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
