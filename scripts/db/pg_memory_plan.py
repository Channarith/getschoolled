#!/usr/bin/env python3
"""PostgreSQL memory plan for the catalog VM (stdlib only; also runs ON the VM at first boot).

The owner's rule is "Postgres uses 90% of the VM's RAM". Taken literally as RESIDENT memory that
invites the kernel OOM killer: one analytic query, a vacuum and a few sorts at the same moment and
the postmaster is gone. So the rule is satisfied the way Postgres is designed to use RAM:

    ~90% of RAM  =  worst-case resident memory (hard-capped at 65%)  +  kernel page cache (the rest)

Postgres reads and writes through the kernel page cache, and effective_cache_size (88% of RAM) tells
the planner to count on it. The page cache is reclaimable instantly, so it can never cause an OOM;
the resident part is what could, so it is the part that is budgeted and asserted.

  python3 scripts/db/pg_memory_plan.py --ram-gb 8                 # human readable
  python3 scripts/db/pg_memory_plan.py --ram-mb auto --cores auto --format conf     # postgresql.conf lines
  python3 scripts/db/pg_memory_plan.py --ram-gb 8 --format sysctl|env|json|table

Exit status 2 (and a message on stderr) when the numbers cannot satisfy the resident cap: it never
prints a configuration it knows is unsafe.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Dict, List

TARGET_PCT = 90.0          # resident + page cache
RESIDENT_CAP_PCT = 65.0    # worst-case resident, asserted
MB = 1
GB = 1024


class PlanError(Exception):
    """The requested machine cannot be configured safely."""


def _down(value: float, step: int) -> int:
    return max(step, int(value // step) * step)


@dataclass
class Plan:
    ram_mb: int
    cores: int
    settings: Dict[str, str] = field(default_factory=dict)
    sysctl: Dict[str, str] = field(default_factory=dict)
    pgbouncer_pool_size: int = 0
    nr_hugepages_estimate: int = 0
    swap_file_mb: int = 0
    budget_mb: Dict[str, int] = field(default_factory=dict)
    resident_worst_mb: int = 0
    resident_worst_pct: float = 0.0
    page_cache_room_mb: int = 0
    target_mb: int = 0
    notes: List[str] = field(default_factory=list)


def plan(
    ram_mb: int,
    cores: int,
    *,
    nodes_per_query: int = 2,
    gather_workers: int = 2,
    pool_size: int = 0,
    resident_cap_pct: float = RESIDENT_CAP_PCT,
    target_pct: float = TARGET_PCT,
) -> Plan:
    """Compute the settings. Raises PlanError if worst-case resident memory would exceed the cap."""
    if ram_mb < 2048:
        raise PlanError(f"{ram_mb} MB of RAM is too small for a 1M-course catalog database (minimum 2048 MB)")
    if cores < 1:
        raise PlanError("cores must be >= 1")

    shared_buffers = _down(ram_mb * 0.375, 128)                  # 35-40% of RAM
    effective_cache = _down(ram_mb * 0.88, 128)                  # 85-90% of RAM
    pool = pool_size or min(64, max(8, cores * 3))               # PgBouncer server connections
    max_connections = pool + 20                                   # + superuser reserve and direct admin sessions
    superuser_reserved = 3
    hash_mem_multiplier = 1.5
    # work_mem: 8% of RAM split across every connection x every sort/hash node that can run at once
    # (parallel workers each take their own work_mem), derated by hash_mem_multiplier so an
    # all-hash worst case still fits the same 8%.
    nodes = nodes_per_query * (1 + gather_workers)
    work_budget = ram_mb * 0.08
    work_mem = int(work_budget / (pool * nodes * hash_mem_multiplier))
    work_mem = max(4, min(256, work_mem))
    maintenance_work_mem = min(2048, _down(ram_mb * 0.025, 16))   # 2.5% of RAM, capped
    autovacuum_max_workers = 3
    autovacuum_work_mem = min(1024, _down(ram_mb * 0.015, 16))    # 1.5% each, x3 workers
    wal_buffers = max(16, min(64, shared_buffers // 32))
    temp_buffers = 4

    worst = {
        "shared_buffers": shared_buffers,
        "work_mem_all_nodes": int(math.ceil(work_mem * nodes * hash_mem_multiplier * pool)),
        "maintenance_work_mem": maintenance_work_mem,
        "autovacuum_workers": autovacuum_work_mem * autovacuum_max_workers,
        "wal_buffers": wal_buffers,
        "temp_buffers_all_conns": temp_buffers * pool,
        "backend_overhead": 5 * max_connections,                  # ~5 MB per backend (catalog caches)
        "background_processes": 150,                              # checkpointer, bgwriter, walwriter, launcher, stats
        "pgbouncer": 64,
        "os_and_systemd": 350 + int(ram_mb * 0.01),
    }
    resident = sum(worst.values())
    pct = 100.0 * resident / ram_mb
    if pct > resident_cap_pct:
        raise PlanError(
            f"worst-case resident memory {resident} MB is {pct:.1f}% of {ram_mb} MB, over the "
            f"{resident_cap_pct:.0f}% cap: this machine is too small for pool={pool}, "
            f"work_mem={work_mem} MB. Use a bigger plan or a smaller PgBouncer pool (--pool-size)."
        )

    huge = int(math.ceil(shared_buffers * 1.07 / 2)) + 8          # 2 MB pages; setup replaces this with the exact value
    swap = max(1024, min(4096, ram_mb // 8))
    out = Plan(ram_mb=ram_mb, cores=cores)
    out.settings = {
        "shared_buffers": f"{shared_buffers}MB",
        "huge_pages": "try",
        "effective_cache_size": f"{effective_cache}MB",
        "work_mem": f"{work_mem}MB",
        "hash_mem_multiplier": f"{hash_mem_multiplier:g}",
        "maintenance_work_mem": f"{maintenance_work_mem}MB",
        "autovacuum_work_mem": f"{autovacuum_work_mem}MB",
        "autovacuum_max_workers": str(autovacuum_max_workers),
        "wal_buffers": f"{wal_buffers}MB",
        "temp_buffers": f"{temp_buffers}MB",
        "max_connections": str(max_connections),
        "superuser_reserved_connections": str(superuser_reserved),
        "max_worker_processes": str(cores),
        "max_parallel_workers": str(cores),
        "max_parallel_workers_per_gather": str(gather_workers),
        "max_parallel_maintenance_workers": "2",
    }
    out.sysctl = {
        "vm.swappiness": "1",
        "vm.overcommit_memory": "0",            # heuristic: see docs/catalog-db.txt for why not 2
        "vm.vfs_cache_pressure": "50",
        "vm.dirty_background_ratio": "5",
        "vm.dirty_ratio": "15",
        "vm.nr_hugepages": str(huge),
    }
    out.pgbouncer_pool_size = pool
    out.nr_hugepages_estimate = huge
    out.swap_file_mb = swap
    out.budget_mb = worst
    out.resident_worst_mb = resident
    out.resident_worst_pct = round(pct, 1)
    out.target_mb = int(ram_mb * target_pct / 100)
    out.page_cache_room_mb = max(0, out.target_mb - resident)
    out.notes = [
        f"worst-case resident {resident} MB = {pct:.1f}% of RAM (cap {resident_cap_pct:.0f}%)",
        f"page cache room up to the {target_pct:.0f}% target: {out.page_cache_room_mb} MB "
        f"(effective_cache_size says {effective_cache} MB = {100 * effective_cache / ram_mb:.0f}%)",
        f"PgBouncer pool_size={pool}; max_connections={max_connections}; work_mem nodes per connection={nodes}",
    ]
    return out


def read_meminfo_mb(path: str = "/proc/meminfo") -> int:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    raise PlanError(f"MemTotal not found in {path}")


def render_conf(p: Plan) -> str:
    lines = [f"# Generated by pg_memory_plan.py for {p.ram_mb} MB RAM / {p.cores} cores. Do not edit: re-run catalog-db-setup.",
             f"# worst-case resident {p.resident_worst_mb} MB ({p.resident_worst_pct}% of RAM, cap {RESIDENT_CAP_PCT:.0f}%); the rest of the {TARGET_PCT:.0f}% target is kernel page cache."]
    lines += [f"{k} = {v}" for k, v in p.settings.items()]
    return "\n".join(lines) + "\n"


def render_sysctl(p: Plan) -> str:
    return "\n".join(f"{k} = {v}" for k, v in p.sysctl.items()) + "\n"


def render_env(p: Plan) -> str:
    return (f"PGB_POOL_SIZE={p.pgbouncer_pool_size}\nPG_HUGEPAGES_ESTIMATE={p.nr_hugepages_estimate}\n"
            f"PG_SWAP_MB={p.swap_file_mb}\nPG_RAM_MB={p.ram_mb}\n"
            f"PG_MEMORY_HIGH_MB={int(p.ram_mb * 0.92)}\nPG_MEMORY_MAX_MB={int(p.ram_mb * 0.97)}\n")


def render_text(p: Plan) -> str:
    out = [f"RAM {p.ram_mb} MB, {p.cores} cores", ""]
    out += [f"  {k:34s} {v}" for k, v in p.settings.items()]
    out += ["", "worst-case resident budget (MB):"]
    out += [f"  {k:34s} {v:6d}" for k, v in p.budget_mb.items()]
    out += [f"  {'TOTAL':34s} {p.resident_worst_mb:6d}  = {p.resident_worst_pct}% of RAM (cap {RESIDENT_CAP_PCT:.0f}%)", ""]
    out += [f"  {n}" for n in p.notes]
    return "\n".join(out) + "\n"


def render_table(sizes: List[tuple]) -> str:
    rows = [plan(ram * GB, cores) for ram, cores in sizes]
    cols = ["shared_buffers", "effective_cache_size", "work_mem", "maintenance_work_mem", "autovacuum_work_mem", "max_connections"]
    head = f"{'':22s}" + "".join(f"{f'{p.ram_mb // GB} GB / {p.cores} vCPU':>16s}" for p in rows)
    lines = [head]
    for c in cols:
        lines.append(f"{c:22s}" + "".join(f"{p.settings[c]:>16s}" for p in rows))
    lines.append(f"{'pgbouncer pool':22s}" + "".join(f"{p.pgbouncer_pool_size:>16d}" for p in rows))
    lines.append(f"{'nr_hugepages (est.)':22s}" + "".join(f"{p.nr_hugepages_estimate:>16d}" for p in rows))
    lines.append(f"{'worst resident':22s}" + "".join(f"{f'{p.resident_worst_pct}%':>16s}" for p in rows))
    lines.append(f"{'page cache room':22s}" + "".join(f"{p.page_cache_room_mb / GB:>13.1f} GB" for p in rows))
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ram-gb", type=float)
    ap.add_argument("--ram-mb", help="integer MB, or 'auto' to read MemTotal from /proc/meminfo")
    ap.add_argument("--cores", default="auto", help="integer or 'auto'")
    ap.add_argument("--pool-size", type=int, default=0, help="override the PgBouncer server pool size")
    ap.add_argument("--format", choices=["text", "conf", "sysctl", "env", "json", "table"], default="text")
    args = ap.parse_args(argv)
    try:
        if args.format == "table":
            sys.stdout.write(render_table([(8, 4), (16, 6), (32, 8), (64, 16)]))
            return 0
        if args.ram_gb is not None:
            ram = int(args.ram_gb * GB)
        elif args.ram_mb in (None, "auto"):
            ram = read_meminfo_mb()
        else:
            ram = int(args.ram_mb)
        cores = (os.cpu_count() or 1) if args.cores == "auto" else int(args.cores)
        p = plan(ram, cores, pool_size=args.pool_size)
    except PlanError as exc:
        print(f"pg_memory_plan: REFUSING TO PLAN: {exc}", file=sys.stderr)
        return 2
    render = {"text": render_text, "conf": render_conf, "sysctl": render_sysctl, "env": render_env,
              "json": lambda x: json.dumps(asdict(x), indent=2) + "\n"}[args.format]
    sys.stdout.write(render(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
