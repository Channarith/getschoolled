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
class Owner:
    """Who a process belongs to. Filled from the probe's [owners] block; every field may be empty."""
    pid: int
    cwd: str = ""
    git_top: str = ""
    worktree: bool = False
    branch: str = ""
    commit: str = ""
    subject: str = ""
    cgroup: str = ""
    chain: list[tuple[int, str]] = field(default_factory=list)  # pid:comm from the process up to init
    env: dict[str, str] = field(default_factory=dict)
    env_readable: bool = False
    log_path: str = ""
    log_mtime: int | None = None

    @property
    def unit(self) -> str:
        """systemd unit or scope from the cgroup path ('' when the process is in a plain session scope)."""
        for part in reversed(self.cgroup.split("/")):
            if part.endswith((".service", ".scope")) and not part.startswith(("session-", "user@")):
                return part
        return ""


@dataclass
class Sock:
    state: str
    local_addr: str
    local_port: int
    peer_addr: str
    peer_port: int
    pids: list[int] = field(default_factory=list)


@dataclass
class Sample:
    """Two readings of a process a few seconds apart: cumulative CPU ticks and read+write bytes."""
    ticks0: int | None = None
    ticks1: int | None = None
    io0: int | None = None
    io1: int | None = None


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
    queue: dict[str, Any] = field(default_factory=dict)  # scripts/fleet/queue.py status --compact
    batch_logs: list[dict[str, Any]] = field(default_factory=list)
    timers: list[str] = field(default_factory=list)
    now: int = 0
    owners: dict[int, Owner] = field(default_factory=dict)
    tmux_panes: list[tuple[int, str, str]] = field(default_factory=list)  # (pane shell pid, session, window)
    sockets: list[Sock] = field(default_factory=list)
    samples: dict[int, Sample] = field(default_factory=dict)
    sample_interval: int = 0
    clk_tck: int = 100
    cur_owner: int = field(default=-1, repr=False)


_SS_PID = re.compile(r"pid=(\d+)")


def parse_ss_line(line: str) -> Sock | None:
    """`ss -H -tanp` row: STATE RECV SEND LOCAL PEER [users:((\"name\",pid=N,fd=M))]."""
    parts = line.split(None, 5)
    if len(parts) < 5 or parts[0] not in ("LISTEN", "ESTAB"):
        return None
    try:
        l_addr, _, l_port = parts[3].rpartition(":")
        p_addr, _, p_port = parts[4].rpartition(":")
        return Sock(parts[0], l_addr, int(l_port), p_addr, int(p_port) if p_port.isdigit() else 0,
                    [int(m) for m in _SS_PID.findall(parts[5])] if len(parts) > 5 else [])
    except ValueError:
        return None


def _int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


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
        elif section == "queue":
            if line.startswith("{"):
                try:
                    rep.queue = json.loads(line)
                except json.JSONDecodeError:
                    rep.queue = {"_state": "QUEUE_BAD_JSON"}
            elif line.startswith("QUEUE_"):
                rep.queue = {"_state": line.split()[0]}
        elif section == "owners":
            _parse_owner_line(rep, line)
        elif section == "tmux":
            parts = line.split(None, 2)
            if len(parts) >= 2 and parts[0].isdigit():
                rep.tmux_panes.append((int(parts[0]), parts[1], parts[2] if len(parts) > 2 else ""))
        elif section == "sockets":
            sock = parse_ss_line(line)
            if sock:
                rep.sockets.append(sock)
        elif section == "sample":
            _parse_sample_line(rep, line)
    return rep


def _parse_owner_line(rep: HostReport, line: str) -> None:
    key, _, value = line.partition("=")
    if key == "pid":
        pid = _int_or_none(value.strip())
        if pid is not None:
            rep.owners[pid] = Owner(pid=pid)
            rep.cur_owner = pid
        return
    cur = rep.owners.get(rep.cur_owner)
    if cur is None:
        return
    if key == "cwd":
        cur.cwd = value
    elif key == "git":
        top, _, rest = value.partition("|")
        wt, _, rest = rest.partition("|")
        branch, _, rest = rest.partition("|")
        commit, _, subject = rest.partition("|")
        cur.git_top, cur.worktree, cur.branch, cur.commit, cur.subject = top, wt == "1", branch, commit, subject
    elif key == "cgroup":
        cur.cgroup = value.rpartition(":")[2] if ":" in value else value
    elif key == "chain":
        for item in value.split():
            pid_s, _, comm = item.partition(":")
            if pid_s.isdigit():
                cur.chain.append((int(pid_s), comm))
    elif key == "env":
        state, _, rest = value.partition("|")
        cur.env_readable = state == "readable"
        for pair in rest.split():
            k, _, v = pair.partition("=")
            if k in ("NLLB_DEVICE", "CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES"):
                cur.env[k] = v
    elif key == "log":
        path, _, mtime = value.rpartition("|")
        cur.log_path, cur.log_mtime = path, _int_or_none(mtime)


def _parse_sample_line(rep: HostReport, line: str) -> None:
    if line.startswith("interval="):
        rep.sample_interval = int(_num(line[9:]) or 0)
    elif line.startswith("clk_tck="):
        rep.clk_tck = int(_num(line[8:]) or 100)
    elif line.startswith(("t0 ", "t1 ")):
        parts = line.split()
        if len(parts) >= 4 and parts[1].isdigit():
            s = rep.samples.setdefault(int(parts[1]), Sample())
            ticks, io = _int_or_none(parts[2]), _int_or_none(parts[3])
            if parts[0] == "t0":
                s.ticks0, s.io0 = ticks, io
            else:
                s.ticks1, s.io1 = ticks, io


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


# ---- who owns a process, and is it working or spinning --------------------------------------

SERVING_LOG_WINDOW_S = 300        # a log write this recent counts as live work
SERVING_IO_BYTES = 256 * 1024     # more read+write than this in the sample window counts as live work
SPINNING_MIN_CPU_PCT = 100.0      # measured CPU (not the lifetime average) needed to call it spinning
GPU_IDLE_UTIL_PCT = 5.0
GPU_IDLE_MIN_BUSY_CORES = 4.0
TOP_PROC_MIN_CPU_PCT = 50.0
TOP_PROC_COUNT = 3


def tmux_session_for(rep: HostReport, pid: int) -> tuple[str, str] | None:
    """(session, window) if pid or any ancestor is a tmux pane's shell; None otherwise."""
    panes = {p: (s, w) for p, s, w in rep.tmux_panes}
    owner = rep.owners.get(pid)
    for anc, _comm in (owner.chain if owner else []):
        if anc in panes:
            return panes[anc]
    return panes.get(pid)


def started_via_gs_run(rep: HostReport, pid: int) -> bool:
    """True if pid or an ancestor is the wrapper or child of a running gs_run job record."""
    mine: set[int] = set()
    for job in rep.jobs:
        if job.get("state") == "running":
            for key in ("pid", "child_pid"):
                if isinstance(job.get(key), int):
                    mine.add(job[key])
    owner = rep.owners.get(pid)
    return pid in mine or any(anc in mine for anc, _ in (owner.chain if owner else []))


def owner_text(rep: HostReport, pid: int) -> str:
    """One line: tmux session | worktree (branch @ commit) | unit | cwd. 'unknown' if the probe saw nothing."""
    o = rep.owners.get(pid)
    if o is None:
        return "unknown (not probed)"
    bits: list[str] = []
    tm = tmux_session_for(rep, pid)
    if tm:
        bits.append(f"tmux '{tm[0]}'" + (f" window '{tm[1]}'" if tm[1] else ""))
    if started_via_gs_run(rep, pid):
        bits.append("started via gs_run")
    if o.git_top:
        name = Path(o.git_top).name
        kind = "worktree" if o.worktree else "repo"
        bits.append(f"{kind} {name} ({o.branch} @ {o.commit}{' ' + repr(o.subject[:40]) if o.subject else ''})")
    if o.unit:
        bits.append(f"unit {o.unit}")
    if o.cwd and not o.git_top:
        bits.append(f"cwd {o.cwd}")
    return " | ".join(bits) if bits else "unknown (no tmux, repo or unit found)"


def chain_text(rep: HostReport, pid: int) -> str:
    o = rep.owners.get(pid)
    if not o or not o.chain:
        return ""
    return " < ".join(f"{p}:{c}" for p, c in o.chain)


def env_text(rep: HostReport, pid: int) -> str:
    o = rep.owners.get(pid)
    if not o:
        return ""
    if not o.env_readable:
        return "environment unreadable (other user)"
    return " ".join(f"{k}={o.env.get(k, '(unset)')}" for k in ("NLLB_DEVICE", "CUDA_VISIBLE_DEVICES"))


def serving_info(rep: HostReport, pid: int) -> dict[str, Any]:
    """Ports this pid listens on, how many ESTABLISHED clients are connected to them, last log write age."""
    ports = sorted({s.local_port for s in rep.sockets if s.state == "LISTEN" and pid in s.pids})
    clients = [s for s in rep.sockets if s.state == "ESTAB" and s.local_port in ports]
    o = rep.owners.get(pid)
    log_age = None
    if o and o.log_mtime and rep.now:
        log_age = max(0, rep.now - o.log_mtime)
    return {"ports": ports, "clients": len(clients), "log_age_s": log_age}


def measured_cpu_pct(rep: HostReport, pid: int) -> float | None:
    s = rep.samples.get(pid)
    if not s or s.ticks0 is None or s.ticks1 is None or rep.sample_interval <= 0:
        return None
    return (s.ticks1 - s.ticks0) / max(1, rep.clk_tck) / rep.sample_interval * 100.0


def io_delta_bytes(rep: HostReport, pid: int) -> int | None:
    s = rep.samples.get(pid)
    if not s or s.io0 is None or s.io1 is None:
        return None
    return s.io1 - s.io0


def classify_busy(rep: HostReport, pid: int) -> tuple[str, str]:
    """('busy-serving' | 'possible-runaway' | 'unverified', reason) for a high-CPU process.

    Serving evidence: connected clients, a recent log write, or real IO during the sample.
    A runaway needs the opposite on every count AND measured CPU still high: with no sample, or
    IO counters that cannot be read, we say 'unverified' and never suggest a kill.
    """
    info = serving_info(rep, pid)
    cpu_now = measured_cpu_pct(rep, pid)
    io = io_delta_bytes(rep, pid)
    evidence: list[str] = []
    if info["clients"]:
        port = ",".join(str(p) for p in info["ports"])
        evidence.append(f"serving {info['clients']} client(s) on port {port}")
    if info["log_age_s"] is not None and info["log_age_s"] < SERVING_LOG_WINDOW_S:
        evidence.append(f"last log write {info['log_age_s']} s ago")
    if io is not None and io > SERVING_IO_BYTES:
        evidence.append(f"{io // 1024} KB read/written in the last {rep.sample_interval} s")
    if evidence:
        return "busy-serving", "; ".join(evidence)
    if cpu_now is None:
        return "unverified", "no CPU/IO sample was taken, so working versus spinning cannot be told apart"
    if io is None:
        return "unverified", f"{cpu_now:.0f}% CPU now, but its IO counters are unreadable (other user), so IO growth is unknown"
    if cpu_now >= SPINNING_MIN_CPU_PCT:
        why = f"{cpu_now:.0f}% CPU over {rep.sample_interval} s, no clients, no IO growth ({io} bytes)"
        if info["ports"]:
            why += f", listening on {','.join(str(p) for p in info['ports'])} with nobody connected"
        return "possible-runaway", why
    return "unverified", f"only {cpu_now:.0f}% CPU in the last {rep.sample_interval} s: it has calmed down since the lifetime average was taken"


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
            kind, why = classify_busy(rep, p.pid)
            who = owner_text(rep, p.pid)
            base = f"pid {p.pid} at {p.pcpu:.0f}% average CPU for {hours:.1f} h: {p.args[:80]}"
            owned = tmux_session_for(rep, p.pid) is not None or bool(rep.owners.get(p.pid) and rep.owners[p.pid].worktree)
            if kind == "busy-serving":
                out.append(Finding(INFO, name, "BUSY_SERVING",
                                   f"{base}. Busy-serving: {why}. Not a kill suggestion. Owner: {who}", ""))
            else:
                label = "Possible runaway" if kind == "possible-runaway" else "High CPU, unverified"
                code = "POSSIBLE_RUNAWAY" if kind == "possible-runaway" else "HIGH_CPU_UNVERIFIED"
                guard = " --i-know-owner" if owned else ""
                fix = (f"ask the owner first ({who}). If it is yours: scripts/fleet_reap.sh --pid {p.pid}{guard} --yes"
                       if kind == "possible-runaway"
                       else f"find out what it is doing first: scripts/fleet_status.sh --host {name}  (owner: {who})")
                out.append(Finding(WARN, name, code, f"{base}. {label}: {why}. Owner: {who}", fix))

    for z in rep.zombies:
        parent = rep.zombie_parents.get(z.ppid)
        pdesc = f"parent pid {z.ppid} {parent.args[:70]}" if parent else f"parent pid {z.ppid}"
        powner = owner_text(rep, z.ppid) if z.ppid in rep.owners else ""
        if powner:
            pdesc += f" [{powner}]"
        if z.ppid == 1:
            fix = "the parent is init, which reaps it; if it stays, reboot"
        elif tmux_session_for(rep, z.ppid) or (z.ppid in rep.owners and rep.owners[z.ppid].worktree):
            fix = (f"the parent belongs to someone else's session: ask the owner. "
                   f"scripts/fleet_reap.sh --pid {z.ppid} --i-know-owner --yes only if you are sure")
        else:
            fix = f"kill -TERM {z.ppid}   (a zombie cannot be killed; its parent must exit or reap it)"
        out.append(Finding(WARN, name, "ZOMBIE", f"defunct pid {z.pid} ({z.args[:40]}), {pdesc}", fix))

    for o in rep.orphans:
        heavy = o.pcpu >= ORPHAN_MIN_CPU_PCT or o.rss_kb >= ORPHAN_MIN_RSS_KB
        if o.etime_s >= ORPHAN_MIN_SECONDS and heavy:
            who = owner_text(rep, o.pid)
            owned = tmux_session_for(rep, o.pid) is not None or bool(rep.owners.get(o.pid) and rep.owners[o.pid].worktree)
            fix = (f"it belongs to a tmux session or worktree ({who}): leave it, or ask the owner" if owned
                   else "unmanaged job: start it through scripts/gs_run.sh next time; stop with kill <pid> if unneeded")
            out.append(Finding(WARN, name, "ORPHAN",
                               f"pid {o.pid} (user {o.user}, parent 1) running {o.etime_s / 3600:.1f} h at {o.pcpu:.0f}% CPU, "
                               f"{o.rss_kb // 1048576} GB: {o.args[:70]}. Owner: {who}", fix))

    busy_cores = sum(p.pcpu for p in rep.procs_cpu) / 100.0
    for i, g in enumerate(rep.gpus):
        util = g.get("util")
        if util is not None and util < GPU_IDLE_UTIL_PCT and busy_cores >= GPU_IDLE_MIN_BUSY_CORES:
            heavy = [p for p in rep.procs_cpu if p.pcpu >= 100][:TOP_PROC_COUNT]
            envs = "; ".join(f"pid {p.pid}: {env_text(rep, p.pid) or 'environment not probed'}" for p in heavy)
            out.append(Finding(WARN, name, "GPU_IDLE_CPU_BUSY",
                               f"GPU {util:.0f}% while {busy_cores:.0f} cores busy: check NLLB_DEVICE/CUDA device settings "
                               f"in the process environment. {envs}".strip(),
                               "NLLB_DEVICE=cpu or CUDA_VISIBLE_DEVICES= (empty) keep a job off the GPU on purpose; "
                               "otherwise restart it with the device unset or cuda, through scripts/gs_run.sh"))
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
    out.extend(queue_findings(rep))
    shown = 0
    for p in rep.procs_cpu:
        if shown >= TOP_PROC_COUNT or p.pcpu < TOP_PROC_MIN_CPU_PCT:
            break
        info = serving_info(rep, p.pid)
        serving = (f"listens on {','.join(map(str, info['ports']))}, serving {info['clients']} client(s)"
                   if info["ports"] else "no listening port")
        if info["log_age_s"] is not None:
            serving += f", last log write {info['log_age_s']} s ago"
        parts = [f"pid {p.pid} {p.pcpu:.0f}% CPU {p.rss_kb // 1048576} GB: {p.args[:60]}",
                 f"owner: {owner_text(rep, p.pid)}", serving]
        chain = chain_text(rep, p.pid)
        if chain:
            parts.append(f"chain: {chain}")
        env = env_text(rep, p.pid)
        if env:
            parts.append(env)
        out.append(Finding(INFO, name, "TOP_PROC", " | ".join(parts), ""))
        shown += 1
    out.sort(key=lambda f: _ORDER[f.severity])
    return out


QUEUE_WORKER_STALE_S = 300  # no worker heartbeat for 5 min
QUEUE_IDLE_WITH_WORK_S = 1800  # idle for 30 min while eligible work is waiting


def _age(now: float, ts: float | None) -> str:
    if not ts:
        return "never"
    s = int(now - ts)
    return f"{s // 86400} d ago" if s >= 86400 else f"{s // 3600} h ago" if s >= 3600 else f"{max(0, s) // 60} min ago"


def queue_findings(rep: HostReport) -> list[Finding]:
    """Findings from the machine's job queue (scripts/fleet/queue.py): worker health, stale leases,
    CUDA-blocked GPU work, idle-with-work, dead jobs and a one-line summary."""
    q = rep.queue
    name = rep.name
    if not q:
        return []
    state = q.get("_state")
    if state == "QUEUE_NOT_INSTALLED":
        return [Finding(INFO, name, "QUEUE_NOT_INSTALLED", "the fleet worker is not installed here, so nothing keeps this machine busy",
                        "from a checkout of main: scripts/fleet/install-units.sh --enable-worker")]
    if state == "QUEUE_NOT_STARTED":
        return [Finding(WARN, name, "QUEUE_NOT_STARTED", "the fleet scripts are here but the worker never ran (no queue database)",
                        "scripts/fleet/install-units.sh --enable-worker")]
    if state:
        return [Finding(WARN, name, state, "the queue status could not be read", "scripts/gs_worker.sh status")]
    now = float(q.get("now") or rep.now or 0)
    w = q.get("worker") or {}
    out: list[Finding] = []
    eligible = int(q.get("queued_eligible", 0))
    running = q.get("running") or []
    hb = w.get("heartbeat")
    worker_down = hb is None or (now and now - hb > QUEUE_WORKER_STALE_S)
    if worker_down and (eligible or running or q.get("stale_leases")):
        out.append(Finding(WARN, name, "WORKER_DOWN",
                           f"fleet worker heartbeat {_age(now, hb)}; {eligible} eligible job(s) waiting, {len(running)} recorded as running",
                           "systemctl --user status gs-worker; systemctl --user reset-failed gs-worker && systemctl --user start gs-worker"))
    if q.get("stale_leases"):
        out.append(Finding(WARN, name, "QUEUE_STALE_LEASE",
                           f"{q['stale_leases']} job lease(s) expired and not yet reclaimed (the worker is down or hung)",
                           "systemctl --user restart gs-worker   (it returns them to the queue and stops leftover runners)"))
    blocked = str(w.get("blocked", ""))
    if w.get("state") == "cuda-blocked" or blocked.startswith("cuda"):
        out.append(Finding(CRIT, name, "CUDA_BLOCKED",
                           f"GPU jobs are NOT starting because the CUDA policy check fails: {blocked}",
                           "check the driver/torch build: <venv>/bin/python -c 'import torch; print(torch.cuda.is_available())'; nvidia-smi; "
                           "a kernel update may need a reboot. The worker retries every few minutes by itself."))
    elif blocked and eligible:
        out.append(Finding(INFO, name, "QUEUE_BLOCKED", f"eligible work is waiting but the worker is holding back: {blocked}", ""))
    if eligible and not running and not q.get("paused") and not worker_down:
        last_busy = q.get("last_busy") or 0
        idle_s = now - last_busy if last_busy else q.get("oldest_eligible_age_s", 0)
        if idle_s >= QUEUE_IDLE_WITH_WORK_S:
            out.append(Finding(WARN, name, "IDLE_WITH_WORK",
                               f"nothing has run for {idle_s / 60:.0f} min with {eligible} eligible job(s) waiting"
                               + (f" ({blocked})" if blocked else ""),
                               "scripts/gs_worker.sh status   (shows what blocks it: GPU lock, memory floor, CUDA check, paused)"))
    if q.get("paused"):
        out.append(Finding(INFO, name, "QUEUE_PAUSED", "the queue is paused: no new jobs start", "scripts/gs_worker.sh resume"))
    dead = q.get("dead_24h") or []
    if dead:
        names = ", ".join(sorted({d.get("type", "?") for d in dead}))
        out.append(Finding(WARN, name, "QUEUE_DEAD_JOBS", f"{len(dead)} job(s) gave up in the last 24 h ({names}): {dead[0].get('error', '')[:100]}",
                           "scripts/gs_worker.sh list --state dead; fix the cause, then scripts/gs_worker.sh requeue <id>"))
    succ = q.get("last_success") or {}
    summary = (f"queue: {len(running)} running ({', '.join(r.get('type', '?') for r in running) or 'none'}), {eligible} waiting"
               + (f", blocked: {q['queued_blocked']}" if q.get("queued_blocked") else "")
               + "; last success " + (", ".join(f"{k} {_age(now, v)}" for k, v in sorted(succ.items())) or "none yet"))
    out.append(Finding(INFO, name, "QUEUE_SUMMARY", summary, ""))
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
