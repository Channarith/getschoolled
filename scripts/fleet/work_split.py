#!/usr/bin/env python3
"""Split the demo work (training, translation, voice rendering) across Spark, iBuyPower (kalel) and the Mac.

  work_split.py gather  [--out DIR]                  read-only inventory of every machine in hosts.conf (key-based ssh)
  work_split.py plan    --inventory DIR [--json]     who runs what, in what order, and what starts now
  work_split.py apply   --inventory DIR [--yes]      start the "now" wave on each machine (prints only, without --yes)
  work_split.py collect --machine kalel [--yes]      rsync finished translations back and merge the current ones

Rules the planner enforces (see docs/fleet-work-split.txt):
  * Spark training and its evaluation (tier 0) are pinned to the Spark and ordered first.
  * Then demo translation (km, th, vi, es, zh first) and demo voice rendering (tier 1), then the rest (tier 2).
  * CPU-only work (edge-tts renders, validation) goes to the Mac or iBuyPower first, so the Spark's CPU and memory stay for training.
  * A CUDA job never lands on a machine without CUDA (the Mac has none), and the Mac never takes a GPU lane.
  * Every job runs under scripts/gs_run.sh, so the memory gate, GPU lock and no-orphan cleanup still apply.
    The planner also keeps the summed memory of the jobs it starts now under (available - reserve) per machine.
Key-based ssh only: no passwords are read, stored or sent. A machine that does not answer is skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import _bootstrap  # noqa: E402,F401  (stdlib-only import of aoep_shared)

JOBS_DIR = ROOT / "scripts" / "fleet" / "jobs"
HOSTS_CONF = ROOT / "scripts" / "fleet" / "hosts.conf"
BUDGETS = ROOT / "scripts" / "fleet" / "budgets.conf"
SPEED = {"spark": 1.0, "kalel": 0.5, "mac": 0.15}  # relative throughput; only used to balance, not to gate
DEFAULT_RESERVE_GB = 8.0
REPO_ON = {"spark": "~/code/gs-main", "kalel": "~/getschoolled", "mac": str(ROOT)}  # override: FLEET_REPO_<NAME>
CPU_OFF_SPARK_MIN = 10_000  # planning penalty, not a limit: the Spark still takes CPU work when nothing else can
LANGS_PER_SHARD = 3
MINUTES_PER_LANG = 25  # NLLB on the Spark; scaled by SPEED


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    tier: int  # 0 = Spark training, 1 = demo translation + voice, 2 = everything else
    cmd: tuple[str, ...]
    lane: str = "gpu"  # gpu | cpu
    cuda: bool = False
    roles: tuple[str, ...] = ()  # empty = any machine
    mem_gb: float = 4.0
    est_min: float = 30.0
    timeout_s: int = 14400
    priority: int = 50
    env: tuple[tuple[str, str], ...] = ()
    self_wrapped: bool = False  # the command already goes through gs_run.sh itself


@dataclass
class Machine:
    name: str
    inv: dict
    reserve_gb: float = DEFAULT_RESERVE_GB
    caps: dict = field(default_factory=lambda: {"gpu": 1, "cpu": 1})

    @property
    def usable(self) -> bool:
        return bool(self.inv) and self.inv.get("reachable", True) is not False

    @property
    def has_cuda(self) -> bool:
        return bool(self.inv.get("cuda")) and self.inv.get("os") != "Darwin"

    @property
    def avail_gb(self) -> float:
        return float(self.inv.get("mem_avail_gb") or 0)

    @property
    def total_gb(self) -> float:
        return float(self.inv.get("mem_total_gb") or 0)

    @property
    def start_budget_gb(self) -> float:
        """Memory the jobs started right now may add up to: what is free beyond the gs_run reserve."""
        return max(0.0, self.avail_gb - self.reserve_gb)


def eligible(item: Item, m: Machine) -> str:
    """'' when the machine can run the item, else the reason it cannot."""
    if not m.usable:
        return "unreachable"
    if item.roles and m.name not in item.roles:
        return f"only on {','.join(item.roles)}"
    if item.cuda and not m.has_cuda:
        return "needs CUDA"
    if m.caps.get(item.lane, 0) <= 0:
        return f"no {item.lane} lane"
    if item.mem_gb > m.total_gb - m.reserve_gb:
        return "too big for this machine"
    return ""


def _languages() -> tuple[list[str], list[str]]:
    """(every target language in product order, the demo-critical ones)."""
    from aoep_shared.translation_v2 import TIER1, TIER2, priority_languages
    return priority_languages(), list(TIER1) + list(TIER2)


def build_catalog(jobs_dir: Path = JOBS_DIR, langs: list[str] | None = None, day: str = "") -> list[Item]:
    """The work, as items. Manifest-backed items take roles, CUDA need, priority and timeout from scripts/fleet/jobs/*.json."""
    from aoep_shared.fleet_queue import load_manifest, render_cmd, render_env
    types, _caps, _ = load_manifest(jobs_dir)
    day = day or time.strftime("%Y-%m-%d")

    def from_manifest(name: str, item_id: str, title: str, tier: int, mem: float, est: float, payload=None) -> Item:
        spec = types[name]
        extra = {"python": "python3", "state": "$HOME/.gs-queue"}
        cmd = render_cmd(spec, payload or {}, spec.roles[0] if spec.roles else "spark", "$PWD", "$HOME", day, extra)
        env = tuple(render_env(spec, payload or {}, spec.roles[0] if spec.roles else "spark", "$PWD", "$HOME", day, extra).items())
        return Item(item_id, title, tier, tuple(cmd), spec.resource, spec.needs_cuda, tuple(spec.roles), mem, est,
                    spec.timeout_s, spec.priority, env)

    items = [
        from_manifest("finetune-nightly", "voice-agent-train", "Voice-agent / STEM training cycle", 0, 40, 480),
        from_manifest("frozen-eval", "voice-agent-eval", "Frozen exam on the current base", 0, 20, 60),
        from_manifest("finetune-kalel-nightly", "kalel-small-train", "Kal-el <=4B QLoRA cycle", 0, 10, 240),
        from_manifest("frozen-eval-small", "kalel-frozen-eval", "Kal-el 4-bit frozen exam", 1, 6, 60),
        from_manifest("compare-bases-small", "kalel-base-bakeoff", "Kal-el small-base bake-off", 1, 6, 180),
        from_manifest("grow-train-set", "grow-train-set", "Grow tutor train set (data bottleneck)", 1, 2, 30),
        from_manifest("voice-prep", "kalel-voice-prep", "Kal-el CosyVoice download+denoise", 2, 4, 600),
    ]
    ordered, demo = _languages()
    wanted = langs or ordered
    for i in range(0, len(wanted), LANGS_PER_SHARD):
        group = wanted[i:i + LANGS_PER_SHARD]
        tier = 1 if any(code in demo for code in group) else 2
        items.append(Item(
            f"translate-{'-'.join(group)}", f"Translate all courses into {', '.join(group)}", tier,
            ("scripts/translate_on_machine.sh", "run", "langs:" + ",".join(group)), "gpu", True, (), 14,
            MINUTES_PER_LANG * len(group), 43200, 60 if tier == 1 else 40))
    items += [
        Item("demo-voice-clone", "Render the demo in the enrolled company voice (VoxCPM2)", 1,
             ("scripts/run_voice_clone.sh",), "gpu", True, ("spark",), 16, 30, 7200, 70,
             (("MODELS", "voxcpm2"), ("LANGS", "en,es,zh,vi,th,km,sw,hi")), self_wrapped=True),
        Item("demo-edge-voices", "Render demo voice choices with edge-tts (every tone and blend)", 1,
             ("python3", "-m", "tts_bakeoff.voice_types", "--out", f"runs/{day}-all", "--groups", "blends,styles",
              "--delay", "0.5"), "cpu", False, (), 2, 90, 21600, 65),
        from_manifest("voice-ingest", "voice-ingest", "Voice-data ingest (resumable, yields the GPU)", 2, 14, 600),
        # Reads data/_incoming_<machine>, which `collect` fills on the Mac, so it is pinned there.
        replace(from_manifest("validate-translations", "validate-translations", "Validate the incoming translations", 2, 2, 20),
                roles=("mac",)),
    ]
    return items


def load_inventories(directory: Path, budgets: dict | None = None, caps: dict | None = None) -> dict[str, Machine]:
    machines: dict[str, Machine] = {}
    for path in sorted(Path(directory).glob("*.json")):
        inv = json.loads(path.read_text())
        name = inv.get("name") or path.stem
        reserve = float(((budgets or {}).get(name) or (budgets or {}).get("default") or {}).get("reserve_mem_gb", DEFAULT_RESERVE_GB) or DEFAULT_RESERVE_GB)
        machines[name] = Machine(name, inv, reserve, dict((caps or {}).get(name, {"gpu": 1 if inv.get("cuda") else 0, "cpu": 1})))
    return machines


def plan(items: list[Item], machines: dict[str, Machine]) -> dict:
    """Greedy by earliest finish. Order: tier, then priority, then longest first; Spark wins ties.

    Slots are the lanes (one GPU job at a time, cpu per _caps.json). A slot whose first job starts at 0 is the
    'now' wave, and only jobs whose summed memory fits the machine's start budget and whose GPU lock is free qualify.
    """
    slots: dict[tuple[str, str], list[float]] = {}
    for m in machines.values():
        for lane, cap in m.caps.items():
            busy = 20.0 if (lane == "gpu" and m.inv.get("gpu_lock_held")) else 0.0
            slots[(m.name, lane)] = [busy] * max(0, int(cap))
    assigned: dict[str, list[dict]] = {name: [] for name in machines}
    unplaced: list[dict] = []
    for item in sorted(items, key=lambda i: (i.tier, -i.priority, -i.est_min)):
        best = None
        reasons: dict[str, str] = {}
        for m in machines.values():
            why = eligible(item, m)
            if why:
                reasons[m.name] = why
                continue
            lane_slots = slots[(m.name, item.lane)]
            k = min(range(len(lane_slots)), key=lambda j: lane_slots[j])
            start = lane_slots[k]
            finish = start + item.est_min / SPEED.get(m.name, 0.3)
            # CPU-only work stays off the Spark when another machine can take it: the Spark's CPU and memory belong to training.
            keep_off_spark = item.lane == "cpu" and m.name == "spark"
            rank = (finish + (CPU_OFF_SPARK_MIN if keep_off_spark else 0), 0 if m.name == "spark" else 1)
            if best is None or rank < best[0]:
                best = (rank, m, k, start, finish)
        if best is None:
            unplaced.append({"id": item.id, "tier": item.tier, "reasons": reasons})
            continue
        _, m, k, start, finish = best
        slots[(m.name, item.lane)][k] = finish
        assigned[m.name].append({"item": item, "start_min": round(start), "finish_min": round(finish)})
    waves: dict[str, list[dict]] = {}
    for name, rows in assigned.items():
        m = machines[name]
        budget = m.start_budget_gb if m.avail_gb >= m.reserve_gb else 0.0
        now, nxt = [], []
        for row in rows:
            it: Item = row["item"]
            fits = row["start_min"] == 0 and it.mem_gb <= budget
            if it.lane == "gpu" and m.inv.get("gpu_lock_held"):
                fits = False
            if fits:
                budget -= it.mem_gb
                now.append(row)
            else:
                nxt.append(row)
        waves[name] = {"now": now, "next": nxt}
    return {"waves": waves, "unplaced": unplaced}


def command_line(item: Item) -> str:
    """The shell line to run in the machine's repo: gs_run.sh wrapper unless the script wraps itself."""
    env = " ".join(f"{k}={shlex.quote(v)}" for k, v in item.env)
    body = " ".join(shlex.quote(t) if not t.startswith("$") else t for t in item.cmd)
    if item.self_wrapped:
        return f"{env} {body}".strip()
    gpu = " --gpu" if item.lane == "gpu" else ""
    inner = f"env {env} {body}" if env else body
    return f"scripts/gs_run.sh --name {item.id}{gpu} --timeout {item.timeout_s} -- {inner}"


def repo_for(name: str) -> str:
    return os.environ.get(f"FLEET_REPO_{name.upper()}", REPO_ON.get(name, "~/getschoolled"))


def render(result: dict, machines: dict[str, Machine]) -> str:
    out = []
    for name, w in result["waves"].items():
        m = machines[name]
        out.append(f"== {name}: avail {m.avail_gb:.0f} GB (reserve {m.reserve_gb:.0f}), cuda={m.has_cuda}, "
                   f"gpu lock {'HELD' if m.inv.get('gpu_lock_held') else 'free'}")
        for label in ("now", "next"):
            for row in w[label]:
                it: Item = row["item"]
                out.append(f"  [{label:4}] t{it.tier} {it.id:34} {it.lane:3} {it.mem_gb:>3.0f}GB "
                           f"start+{row['start_min']}m ~{row['finish_min'] - row['start_min']}m")
    for u in result["unplaced"]:
        out.append(f"  [none] t{u['tier']} {u['id']}: {u['reasons']}")
    return "\n".join(out)


# ---------------------------------------------------------------- gather / apply / collect


def parse_hosts(text: str) -> list[tuple[str, str, str, list[str]]]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            rows.append((parts[0], parts[1], parts[2], parts[3].split(",") if len(parts) > 3 else []))
    return rows


def ssh_base(target: str) -> list[str]:
    return ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new", target]


def gather(out_dir: Path, runner=subprocess.run) -> dict[str, bool]:
    out_dir.mkdir(parents=True, exist_ok=True)
    script = (HERE / "inventory.py").read_text()
    status = {}
    for name, user, host, fallbacks in parse_hosts(HOSTS_CONF.read_text()):
        host = os.environ.get(f"FLEET_HOST_{name.upper()}", host)
        inv = None
        if host == "local":
            r = runner([sys.executable, str(HERE / "inventory.py"), "--name", name], capture_output=True, text=True, timeout=120)
            inv = _json_or_none(r.stdout)
        else:
            for h in [host] + fallbacks:
                r = runner(ssh_base(f"{user}@{h}") + ["python3", "-", "--name", name], input=script, capture_output=True,
                           text=True, timeout=150)
                inv = _json_or_none(r.stdout)
                if inv:
                    break
        status[name] = bool(inv)
        (out_dir / f"{name}.json").write_text(json.dumps(inv or {"name": name, "reachable": False}, indent=1) + "\n")
    return status


def _json_or_none(text: str):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def apply(result: dict, machines: dict[str, Machine], yes: bool, runner=subprocess.run) -> list[str]:
    log = []
    hosts = {n: (u, h) for n, u, h, _ in parse_hosts(HOSTS_CONF.read_text())}
    for name, w in result["waves"].items():
        for row in w["now"]:
            it: Item = row["item"]
            line = command_line(it)
            remote = f"cd {repo_for(name)} && mkdir -p ~/.gs-queue/logs && (nohup bash -c {shlex.quote(line)} > ~/.gs-queue/logs/ws-{it.id}.log 2>&1 &)"
            if not yes:
                log.append(f"[dry-run] {name}: {remote}")
                continue
            user, host = hosts.get(name, ("-", "local"))
            host = os.environ.get(f"FLEET_HOST_{name.upper()}", host)
            cmd = ["bash", "-lc", remote] if host == "local" else ssh_base(f"{user}@{host}") + [remote]
            r = runner(cmd, capture_output=True, text=True, timeout=60)
            log.append(f"{name}: {it.id} -> {'started' if r.returncode == 0 else 'FAILED: ' + (r.stderr or '')[:120]}")
    return log


def collect(machine: str, yes: bool, incoming_root: Path, library: Path | None = None, runner=subprocess.run) -> dict:
    """rsync the machine's translations (never deleting anything), then merge only what is current for today's English."""
    from aoep_shared.course_translation_library import library_dir, load_translation, save_translation, safe_course_id
    from aoep_shared.translation_v2 import audio_sources, is_current, studio_sources
    library = library or library_dir()
    incoming = incoming_root / f"_incoming_{machine}"  # the folder validate-translations already reads
    incoming.mkdir(parents=True, exist_ok=True)
    hosts = {n: (u, h) for n, u, h, _ in parse_hosts(HOSTS_CONF.read_text())}
    user, host = hosts.get(machine, ("-", "local"))
    host = os.environ.get(f"FLEET_HOST_{machine.upper()}", host)
    if host != "local":
        src = f"{user}@{host}:~/translations/"
        r = runner(["rsync", "-a", "--ignore-existing", "--exclude", "_work/", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=8", src,
                    str(incoming) + "/"], capture_output=True, text=True, timeout=3600)
        if r.returncode != 0:
            return {"error": f"rsync failed: {(r.stderr or '')[:200]}"}
    sources = {safe_course_id(s.course_id): s for s in list(audio_sources()) + list(studio_sources())}
    counts = {"merged": 0, "already_current": 0, "rejected": 0, "unknown_course": 0}
    rejected = []
    for path in sorted(incoming.glob("*/*.json")):
        if path.parent.name.startswith("_"):  # _work state folders are not translations
            continue
        source = sources.get(path.parent.name)
        if source is None:
            counts["unknown_course"] += 1
            continue
        lang = path.stem
        try:
            record = json.loads(path.read_text())
        except ValueError:
            counts["rejected"] += 1
            rejected.append({"file": str(path), "why": "not json"})
            continue
        ok, why = is_current(record, source, lang)
        if not ok:
            counts["rejected"] += 1
            rejected.append({"file": str(path), "why": why})
            continue
        have, _ = is_current(load_translation(source.course_id, lang, library), source, lang)
        if have:
            counts["already_current"] += 1
            continue
        if yes:
            save_translation(record, library)
        counts["merged"] += 1
    return {"library": str(library), "applied": yes, **counts, "rejected_sample": rejected[:10]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gather")
    g.add_argument("--out", default=str(Path.home() / ".gs-queue" / "inventory"))
    for name in ("plan", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--inventory", default=str(Path.home() / ".gs-queue" / "inventory"))
        p.add_argument("--json", action="store_true")
        if name == "apply":
            p.add_argument("--yes", action="store_true", help="really start the jobs (default: print the commands)")
    c = sub.add_parser("collect")
    c.add_argument("--machine", required=True)
    c.add_argument("--yes", action="store_true", help="really merge into the library (default: report only)")
    c.add_argument("--incoming", default=str(ROOT / "data"), help="parent of _incoming_<machine>")
    args = ap.parse_args(argv)
    if args.cmd == "gather":
        status = gather(Path(args.out))
        print(json.dumps(status))
        return 0 if any(status.values()) else 1
    if args.cmd == "collect":
        result = collect(args.machine, args.yes, Path(args.incoming))
        print(json.dumps(result, indent=1))
        return 1 if "error" in result else 0
    from aoep_shared.fleet_queue import load_manifest
    from aoep_shared.fleet_status import parse_budgets
    budgets = parse_budgets(BUDGETS.read_text()) if BUDGETS.exists() else {}
    _types, caps, _ = load_manifest(JOBS_DIR)
    machines = load_inventories(Path(args.inventory), budgets, caps)
    if not machines:
        print(f"no inventory in {args.inventory}: run `work_split.py gather` first", file=sys.stderr)
        return 2
    result = plan(build_catalog(), machines)
    if args.cmd == "plan":
        if args.json:
            print(json.dumps({n: {k: [{"id": r["item"].id, "start_min": r["start_min"]} for r in v[k]] for k in v}
                              for n, v in result["waves"].items()} | {"unplaced": result["unplaced"]}, indent=1))
        else:
            print(render(result, machines))
        return 0
    for line in apply(result, machines, args.yes):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
