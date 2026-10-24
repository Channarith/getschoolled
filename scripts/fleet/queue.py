#!/usr/bin/env python3
"""Fleet job queue: the worker, and the commands to look at and steer it.

  queue.py worker [--once] [--tick 15]       run the worker for this machine (systemd runs this)
  queue.py status [--json] [--compact]       what is running / waiting / blocked and why
  queue.py list [--state queued|running|done|dead] [--limit 30]
  queue.py enqueue TYPE [--payload JSON] [--dedupe KEY] [--priority N] [--machine M]
  queue.py cancel ID | requeue ID
  queue.py pause | resume                    stop/allow starting new jobs (running ones are not touched)
  queue.py disable TYPE | enable TYPE        e.g. keep translate-stage off while another session does it
  queue.py cleanup                           stop leftover runners this worker started earlier (safe)
  queue.py report [--write]                  human-readable daily summary (--write saves it to ~/.gs-queue/health/)
  queue.py validate                          check the job manifests

Environment: GS_QUEUE_DB (default ~/.gs-queue/queue.db), GS_MACHINE (spark|kalel|mac; default: matched
from budgets.conf by hostname), GS_JOBS_DIR, GS_PYTHON (the Python with torch for GPU jobs).
Only processes this worker started are ever signalled.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bootstrap  # noqa: E402,F401  (stdlib-only import of aoep_shared)

from aoep_shared.fleet_queue import ConfigError, Queue, day_stamp, load_manifest  # noqa: E402
from aoep_shared.fleet_status import parse_budgets  # noqa: E402
from aoep_shared.fleet_worker import SubprocessRunner, Worker, WorkerConfig, find_python  # noqa: E402

HOME = str(Path.home())
STATE_DIR = Path(os.environ.get("GS_STATE_DIR", f"{HOME}/.gs-queue"))
DB_PATH = os.environ.get("GS_QUEUE_DB", str(STATE_DIR / "queue.db"))
JOBS_DIR = os.environ.get("GS_JOBS_DIR", str(ROOT / "scripts" / "fleet" / "jobs"))
BUDGETS = ROOT / "scripts" / "fleet" / "budgets.conf"


def detect_machine(hostname: str, budgets: dict[str, dict[str, str]]) -> str:
    forced = os.environ.get("GS_MACHINE", "").strip()
    if forced:
        return forced
    for name, kv in budgets.items():
        if name == "default":
            continue
        if kv.get("match") and re.search(kv["match"], hostname, re.I):
            return name
    return "default"


def machines_by_role(types) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in types.values():
        out[spec.name] = list(spec.roles)
    return out


def build(args=None):
    budgets = parse_budgets(BUDGETS.read_text()) if BUDGETS.exists() else {}
    host = socket.gethostname().split(".")[0]
    machine = detect_machine(host, budgets)
    types, caps, _extra = load_manifest(JOBS_DIR)
    q = Queue(DB_PATH)
    machine_caps = caps.get(machine, {"gpu": 0, "cpu": 1, "net": 1})
    reserve = float(budgets.get(machine, budgets.get("default", {})).get("reserve_mem_gb", "4"))
    cfg = WorkerConfig(
        machine=machine, repo=str(ROOT), home=HOME, python=find_python(str(ROOT), HOME), caps=machine_caps,
        reserve_mem_gb=reserve, cuda_required=(machine == "spark" or os.environ.get("AOEP_HOST_ROLE") == "spark"),
        gpu_lock=os.environ.get("GS_GPU_LOCK", f"{HOME}/.gs-gpu.lock"), logs_dir=str(STATE_DIR / "logs"),
        machines_by_role=machines_by_role(types), hostname=host, state_dir=str(STATE_DIR))
    return q, types, cfg


def cmd_worker(args) -> int:
    q, types, cfg = build()
    Path(cfg.logs_dir).mkdir(parents=True, exist_ok=True)
    worker = Worker(q, types, cfg, SubprocessRunner())
    stop = {"now": False}

    def on_signal(signum, _frame):
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    worker.log(f"worker up: machine={cfg.machine} python={cfg.python} caps={dict(cfg.caps)} reserve={cfg.reserve_mem_gb:g}GB "
               f"cuda_required={cfg.cuda_required} types={sorted(types)}")
    if args.once:
        # Start what is eligible, wait for it to finish (up to --once-wait seconds), and never leave a
        # job running behind us: whatever is still running at the deadline (or on Ctrl-C) is stopped and requeued.
        worker.recover()
        deadline = time.time() + args.once_wait
        try:
            worker.tick()
            while worker.running and time.time() < deadline and not stop["now"]:
                time.sleep(5)
                worker.tick()
        finally:
            worker.shutdown()
        worker.log("once: done")
        return 0
    worker.run_forever(args.tick, lambda: stop["now"])
    return 0


def cmd_status(args) -> int:
    q, types, cfg = build()
    st = q.status(cfg.machine, types, cfg.caps)
    st["role"] = cfg.machine
    if args.json or args.compact:
        print(json.dumps(st, separators=(",", ":")) if args.compact else json.dumps(st, indent=2))
        return 0
    print(render_status(st))
    return 0


def _ago(ts, now) -> str:
    if not ts:
        return "never"
    s = int(now - ts)
    return f"{s // 86400}d ago" if s >= 86400 else f"{s // 3600}h ago" if s >= 3600 else f"{s // 60}m ago"


def render_status(st) -> str:
    now = st["now"]
    w = st.get("worker") or {}
    lines = [f"machine {st['machine']}   worker: {w.get('state', 'not running')}"
             + (f" (heartbeat {_ago(w.get('heartbeat'), now)})" if w else "")
             + ("   PAUSED" if st["paused"] else "")]
    if w.get("blocked"):
        lines.append(f"  blocked: {w['blocked']}")
    lines.append(f"  jobs: {st['counts']}   caps: {st['caps']}")
    for r in st["running"]:
        lines.append(f"  running  #{r['id']} {r['type']} ({r['resource']}, prio {r['priority']}) started {_ago(r['started'], now)}")
    lines.append(f"  waiting and eligible now: {st['queued_eligible']}   blocked: {st['queued_blocked'] or 'none'}")
    if st["stale_leases"]:
        lines.append(f"  STALE LEASES: {st['stale_leases']} (worker is down or hung)")
    if st["disabled"]:
        lines.append(f"  disabled types: {', '.join(st['disabled'])}")
    for t, ts in sorted(st["last_success"].items()):
        lines.append(f"  last success {t}: {_ago(ts, now)}")
    for d in st["dead_24h"]:
        lines.append(f"  DEAD #{d['id']} {d['type']}: {d['error']}")
    return "\n".join(lines)


def cmd_list(args) -> int:
    q, types, cfg = build()
    where, params = ("WHERE state=?", [args.state]) if args.state else ("", [])
    for r in q.db.execute(f"SELECT * FROM jobs {where} ORDER BY id DESC LIMIT ?", (*params, args.limit)):
        print(f"#{r['id']:<5} {r['state']:<9} {r['type']:<22} prio {r['priority']:<3} att {r['attempts']}/{r['max_attempts']} {r['error'][:70]}")
    return 0


def cmd_enqueue(args) -> int:
    q, types, cfg = build()
    spec = types.get(args.type)
    if spec is None:
        print(f"unknown job type {args.type}; known: {', '.join(sorted(types))}", file=sys.stderr)
        return 64
    payload = json.loads(args.payload) if args.payload else {}
    jid = q.enqueue(spec, payload, dedupe_key=args.dedupe, priority=args.priority, machine=args.machine or cfg.machine)
    print(f"enqueued #{jid}" if jid else "not enqueued: an active job with that dedupe key exists")
    return 0 if jid else 1


def cmd_simple(args) -> int:
    q, types, cfg = build()
    if args.cmd == "cancel":
        print("cancelled" if q.cancel(args.id) else "not cancelled (only queued jobs can be cancelled; stop a running one with pause + the worker)")
    elif args.cmd == "requeue":
        print("requeued" if q.requeue(args.id) else "not requeued")
    elif args.cmd in ("pause", "resume"):
        q.set_setting("paused", args.cmd == "pause")
        print(args.cmd + "d: no NEW jobs will start" if args.cmd == "pause" else "resumed")
    elif args.cmd in ("disable", "enable"):
        if args.type not in types:
            print(f"unknown job type {args.type}", file=sys.stderr)
            return 64
        cur = q.disabled_types()
        (cur.add if args.cmd == "disable" else cur.discard)(args.type)
        q.set_setting("disabled_types", sorted(cur))
        print(f"{args.cmd}d {args.type}; disabled now: {sorted(cur) or 'none'}")
    elif args.cmd == "prune":
        print(f"pruned {q.prune()} old job(s)")
    return 0


def cmd_cleanup(args) -> int:
    q, types, cfg = build()
    worker = Worker(q, types, cfg, SubprocessRunner())
    n = worker.recover()
    print(f"cleanup: returned {n} job(s) to the queue (only runners recorded by this worker were stopped)")
    return 0


def cmd_report(args) -> int:
    q, types, cfg = build()
    st = q.status(cfg.machine, types, cfg.caps)
    since = st["now"] - 86400
    rows = q.db.execute("SELECT type, state, COUNT(*) n, SUM(finished-started) busy FROM jobs WHERE finished>? GROUP BY type, state", (since,)).fetchall()
    out = [f"Fleet health, machine {cfg.machine}, {day_stamp(st['now'])}", "", render_status(st), "", "Last 24 hours:"]
    for r in rows:
        out.append(f"  {r['type']:<22} {r['state']:<8} x{r['n']}  busy {int((r['busy'] or 0) // 60)} min")
    idle = st["now"] - (st["last_busy"] or 0)
    out.append(f"  last time any job was running: {int(idle // 60)} min ago")
    text = "\n".join(out) + "\n"
    if args.write:
        d = STATE_DIR / "health"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"fleet-{day_stamp(st['now'])}.txt"
        path.write_text(text)
        for old in sorted(d.glob("fleet-*.txt"))[:-30]:
            old.unlink()
        print(f"wrote {path}")
    else:
        print(text)
    return 0


def cmd_validate(args) -> int:
    try:
        types, caps, _ = load_manifest(JOBS_DIR)
    except ConfigError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"ok: {len(types)} job types ({', '.join(sorted(types))}); caps for {', '.join(sorted(caps))}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("worker"); p.add_argument("--once", action="store_true"); p.add_argument("--once-wait", type=int, default=3600, help="with --once: seconds to wait for jobs")
    p.add_argument("--tick", type=float, default=15.0); p.set_defaults(fn=cmd_worker)
    p = sub.add_parser("status"); p.add_argument("--json", action="store_true"); p.add_argument("--compact", action="store_true"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("list"); p.add_argument("--state"); p.add_argument("--limit", type=int, default=30); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("enqueue"); p.add_argument("type"); p.add_argument("--payload"); p.add_argument("--dedupe")
    p.add_argument("--priority", type=int); p.add_argument("--machine"); p.set_defaults(fn=cmd_enqueue)
    for name in ("cancel", "requeue"):
        p = sub.add_parser(name); p.add_argument("id", type=int); p.set_defaults(fn=cmd_simple)
    for name in ("pause", "resume", "prune"):
        p = sub.add_parser(name); p.set_defaults(fn=cmd_simple)
    for name in ("disable", "enable"):
        p = sub.add_parser(name); p.add_argument("type"); p.set_defaults(fn=cmd_simple)
    p = sub.add_parser("cleanup"); p.set_defaults(fn=cmd_cleanup)
    p = sub.add_parser("report"); p.add_argument("--write", action="store_true"); p.set_defaults(fn=cmd_report)
    p = sub.add_parser("validate"); p.set_defaults(fn=cmd_validate)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
