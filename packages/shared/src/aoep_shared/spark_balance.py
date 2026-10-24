"""Memory and GPU balance monitor for the DGX Spark (replaces the hand-made gpu-balance-monitor.sh).

What it protects: STEM/CosyVoice fine-tunes and the nightly share the GB10's unified memory with a 35B llama-server
(the bake-off's model) and a YouTube ingest. Two jobs:
  * pause yt-dlp (SIGSTOP) when free memory is low, resume when it recovers;
  * stop the bake-off client only when it is demonstrably starved by a fine-tune AND memory is actually short.

What was wrong with the first version (see docs/fleet-ops.txt, Spark services):
  1. any non-llama GPU process over 2 GiB counted as "training", so evaluate.py (an evaluation) made it kill the
     bake-off. Processes are now classified by command line: fine-tune, evaluation, bake-off client.
  2. the decode-rate window started when the client connected, which is exactly when a sleeping llama-server is
     reloading ~20 GB from disk, so the client was killed at every cycle ("14 tokens in 7305 s"). Now nothing is
     measured until the server reports ready (/health 200, /slots reachable, not sleeping), a grace period follows
     every wake, and the rate window starts at the first decoded token.
  3. no memory floor: it killed with 70 GB free. Now a kill needs free memory under a floor.

The decision logic is pure (step) so it is tested against fake samples; System wraps the real machine.
"""
from __future__ import annotations

import argparse
import atexit
import json
import logging
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---- classification ---------------------------------------------------------------------------------------
FINETUNE_RE = re.compile(r"(?:^|[\s/])(?:run_finetune\.py|train\.py|spark_cosyvoice\S*train\S*)(?:\s|$)")
EVAL_RE = re.compile(r"(?:^|[\s/])evaluate\.py(?:\s|$)")
DEFAULT_BAKEOFF = r"spark_serve_eval\.py|nightly_candidates\.py|rag_small_evals\.py"
DEFAULT_INGEST = r"yt-dlp|yt_dlp"

FINETUNE, EVAL, BAKEOFF, OTHER = "finetune", "eval", "bakeoff", "other"


def classify(cmd: str, bakeoff_re: Optional[re.Pattern] = None) -> str:
    """finetune | eval | bakeoff | other, from a process command line (never from GPU memory size)."""
    bake = bakeoff_re or re.compile(DEFAULT_BAKEOFF)
    if bake.search(cmd):
        return BAKEOFF
    if FINETUNE_RE.search(cmd):
        return FINETUNE
    if EVAL_RE.search(cmd):
        return EVAL
    return OTHER


# ---- configuration (every threshold is an environment variable) --------------------------------------------
def _env_num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


@dataclass(frozen=True)
class Config:
    free_low_mb: int = 10240        # below: pause the ingest
    free_ok_mb: int = 16384         # above: resume it
    kill_floor_mb: int = 24576      # a starved bake-off may be stopped during a fine-tune only below this
    critical_mb: int = 6144         # below this the bake-off may be stopped even during an evaluation
    window_s: int = 180             # decode-rate window, started at the first decoded token
    starve_tok_s: float = 0.25      # starved: fewer decoded tokens per second than this over the whole window
    grace_s: int = 600              # after the server wakes (sleeping/loading/down -> ready): never kill
    tick_s: int = 20
    llama_url: str = "http://127.0.0.1:8342"
    bakeoff_pattern: str = DEFAULT_BAKEOFF
    ingest_pattern: str = DEFAULT_INGEST
    log_max_bytes: int = 5_000_000
    log_backups: int = 5

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        return cls(
            free_low_mb=int(_env_num("BALANCE_FREE_LOW_MB", cls.free_low_mb)),
            free_ok_mb=int(_env_num("BALANCE_FREE_OK_MB", cls.free_ok_mb)),
            kill_floor_mb=int(_env_num("BALANCE_KILL_FLOOR_MB", cls.kill_floor_mb)),
            critical_mb=int(_env_num("BALANCE_CRITICAL_MB", cls.critical_mb)),
            window_s=int(_env_num("BALANCE_WINDOW_S", cls.window_s)),
            starve_tok_s=_env_num("BALANCE_STARVE_TOK_S", cls.starve_tok_s),
            grace_s=int(_env_num("BALANCE_GRACE_S", cls.grace_s)),
            tick_s=max(1, int(_env_num("BALANCE_TICK_S", cls.tick_s))),
            llama_url=(e("BALANCE_LLAMA_URL") or cls.llama_url).rstrip("/"),
            bakeoff_pattern=e("BALANCE_BAKEOFF_PATTERN") or cls.bakeoff_pattern,
            ingest_pattern=e("BALANCE_INGEST_PATTERN") or cls.ingest_pattern,
        )


# ---- sample / state / actions ------------------------------------------------------------------------------
@dataclass
class Sample:
    now: float
    free_mb: int
    finetune_pids: List[int] = field(default_factory=list)
    eval_pids: List[int] = field(default_factory=list)
    bakeoff_pids: List[int] = field(default_factory=list)
    server: str = "down"        # ok | loading | sleeping | down
    slots_ok: bool = False
    decoded: int = 0            # max n_decoded over processing slots (0 when idle or no token yet)
    gpu: str = "n/a"

    @property
    def ready(self) -> bool:
        return self.server == "ok" and self.slots_ok


@dataclass
class State:
    was_ready: Optional[bool] = None
    grace_until: float = 0.0
    win_start: Optional[float] = None
    win_base: int = 0
    spared_at: Dict[str, float] = field(default_factory=dict)
    warned: set = field(default_factory=set)


Action = Tuple[str, Dict[str, Any]]


def step(st: State, cfg: Config, s: Sample) -> List[Action]:
    """One decision. Mutates st; returns actions: pause_ingest, resume_ingest, stop_bakeoff, log."""
    acts: List[Action] = []

    if s.free_mb < cfg.free_low_mb:
        acts.append(("pause_ingest", {"free_mb": s.free_mb}))
    elif s.free_mb > cfg.free_ok_mb:
        acts.append(("resume_ingest", {"free_mb": s.free_mb}))

    ready = s.ready
    if ready and st.was_ready is False:
        st.grace_until = s.now + cfg.grace_s
        st.win_start = None
        acts.append(("log", {"event": "server_woke", "grace_s": cfg.grace_s, "server": s.server}))
    if not ready:
        if st.was_ready:
            acts.append(("log", {"event": "server_not_ready", "server": s.server, "slots_ok": s.slots_ok}))
        st.win_start = None
    st.was_ready = ready

    if not s.slots_ok and s.server == "ok" and "slots" not in st.warned:
        st.warned.add("slots")
        acts.append(("log", {"event": "slots_unreachable", "note": "decode-rate rule disabled; only the memory rule can stop the bake-off"}))

    # decode window: only while ready, a bake-off client exists, and a slot has produced its first token
    if ready and s.bakeoff_pids and s.decoded > 0:
        if st.win_start is None or s.decoded < st.win_base:
            st.win_start, st.win_base = s.now, s.decoded
    else:
        st.win_start = None

    if not s.bakeoff_pids:
        return acts

    finetune, evaluating = bool(s.finetune_pids), bool(s.eval_pids)
    in_grace = s.now < st.grace_until
    elapsed = (s.now - st.win_start) if st.win_start is not None else 0.0
    rate = ((s.decoded - st.win_base) / elapsed) if elapsed > 0 else None
    starved = st.win_start is not None and elapsed >= cfg.window_s and rate is not None and rate < cfg.starve_tok_s
    numbers = {
        "free_mb": s.free_mb, "finetune": finetune, "evaluating": evaluating, "in_grace": in_grace,
        "window_s": round(elapsed), "tok_s": None if rate is None else round(rate, 3),
        "pids": list(s.bakeoff_pids), "server": s.server,
    }

    reason = None
    if s.free_mb < cfg.critical_mb:
        reason = "memory_critical"
    elif finetune and starved and s.free_mb < cfg.kill_floor_mb and not in_grace:
        reason = "starved_by_finetune"
    if reason:
        st.win_start = None
        acts.append(("stop_bakeoff", {"reason": reason, **numbers}))
    elif starved and (finetune or evaluating):
        why = "evaluation_not_finetune" if (evaluating and not finetune) else (
            "grace" if in_grace else "memory_not_short")
        last = st.spared_at.get(why, -1e9)
        if s.now - last >= 600:
            st.spared_at[why] = s.now
            acts.append(("log", {"event": "bakeoff_spared", "why": why, **numbers}))
    return acts


# ---- the real machine --------------------------------------------------------------------------------------
class System:
    """Everything the monitor reads or does on the host. Replaced by a fake in tests."""

    def now(self) -> float:
        return time.time()

    def free_mb(self) -> int:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
        return 1 << 30

    def ps(self) -> List[Tuple[int, str]]:
        import subprocess
        out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, check=False).stdout
        rows = []
        for line in out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].isdigit():
                rows.append((int(parts[0]), parts[1]))
        return rows

    def gpu_line(self) -> str:
        import subprocess
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5, check=False).stdout
            return (out.splitlines() or ["n/a"])[0].replace(" ", "") or "n/a"
        except (OSError, Exception):  # noqa: BLE001
            return "n/a"

    def http_get(self, url: str, timeout: float = 3.0) -> Tuple[Optional[int], str]:
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 - local llama-server URL
                return resp.status, resp.read(1_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, ""
        except Exception:  # noqa: BLE001
            return None, ""

    def send(self, pid: int, sig: int) -> bool:
        try:
            os.kill(pid, sig)
            return True
        except OSError:
            return False

    def starttime(self, pid: int) -> Optional[int]:
        """Field 22 of /proc/PID/stat: lets us tell a reused PID from the process we stopped."""
        try:
            raw = Path(f"/proc/{pid}/stat").read_text()
            return int(raw.rsplit(")", 1)[1].split()[19])
        except (OSError, IndexError, ValueError):
            pass
        try:  # no /proc (macOS, used by the tests): the process start time as ps prints it
            import subprocess
            out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, check=False).stdout.strip()
            import zlib  # not hash(): that is randomised per process and would break the persisted list across restarts
            return zlib.crc32(out.encode()) if out else None
        except OSError:
            return None


def parse_decoded(raw: str) -> int:
    """Largest n_decoded across slots that are currently processing (0 when idle / unparsable)."""
    try:
        data = json.loads(raw)
    except ValueError:
        return 0
    if isinstance(data, dict):
        data = [data]
    best = 0
    for slot in data if isinstance(data, list) else []:
        if not isinstance(slot, dict) or not slot.get("is_processing"):
            continue
        for tok in slot.get("next_token") or []:
            try:
                best = max(best, int(tok.get("n_decoded") or 0))
            except (TypeError, ValueError, AttributeError):
                continue
        if "n_decoded" in slot:
            try:
                best = max(best, int(slot["n_decoded"] or 0))
            except (TypeError, ValueError):
                pass
    return best


def probe_server(system: System, base: str) -> Tuple[str, bool, int]:
    """(server state, slots reachable, decoded tokens). /props and /health do not wake a sleeping llama-server."""
    code, raw = system.http_get(base + "/props", 3.0)
    if code == 200:
        try:
            if json.loads(raw).get("is_sleeping"):
                return "sleeping", False, 0
        except ValueError:
            pass
    code, _ = system.http_get(base + "/health", 3.0)
    if code == 200:
        server = "ok"
    elif code == 503:
        return "loading", False, 0
    else:
        return "down", False, 0
    scode, sraw = system.http_get(base + "/slots", 3.0)
    if scode != 200:
        return server, False, 0
    try:
        json.loads(sraw)
    except ValueError:
        return server, False, 0
    return server, True, parse_decoded(sraw)


# ---- the monitor ------------------------------------------------------------------------------------------
class Monitor:
    def __init__(self, system: System, cfg: Config, state_dir: Path, log: Optional[logging.Logger] = None) -> None:
        self.sys, self.cfg, self.dir = system, cfg, Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state = State()
        self.bake_re = re.compile(cfg.bakeoff_pattern)
        self.ingest_re = re.compile(cfg.ingest_pattern)
        self.paused_file = self.dir / "balance.paused.json"
        self.status_file = self.dir / "balance.status"
        self.status_json = self.dir / "balance.status.json"
        self.paused: List[Dict[str, Any]] = self._load_paused()
        self.log = log or self._make_logger()

    # logging: one JSON object per line, rotated
    def _make_logger(self) -> logging.Logger:
        lg = logging.getLogger(f"aoep.spark_balance.{id(self)}")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        fh = RotatingFileHandler(self.dir / "balance.jsonl", maxBytes=self.cfg.log_max_bytes, backupCount=self.cfg.log_backups)
        fh.setFormatter(logging.Formatter("%(message)s"))
        lg.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(message)s"))
        lg.addHandler(sh)
        return lg

    def emit(self, event: str, **fields: Any) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(self.sys.now())), "event": event, **fields}
        self.log.info(json.dumps(rec, sort_keys=True, default=str))

    # persisted list of processes we SIGSTOPped: survives a crash or restart of the monitor
    def _load_paused(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self.paused_file.read_text())
            return [d for d in data if isinstance(d, dict) and "pid" in d]
        except (OSError, ValueError):
            return []

    def _save_paused(self) -> None:
        tmp = self.paused_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.paused))
        os.replace(tmp, self.paused_file)

    def _still_ours(self, entry: Dict[str, Any]) -> bool:
        st = self.sys.starttime(int(entry["pid"]))
        return st is not None and st == entry.get("start")

    def pause_ingest(self, procs: List[Tuple[int, str]], free_mb: int) -> None:
        have = {int(e["pid"]) for e in self.paused}
        for pid, cmd in procs:
            if pid in have or pid == os.getpid() or not self.ingest_re.search(cmd):
                continue
            start = self.sys.starttime(pid)
            if start is None or not self.sys.send(pid, signal.SIGSTOP):
                continue
            self.paused.append({"pid": pid, "start": start, "cmd": cmd[:120]})
            self.emit("ingest_paused", pid=pid, free_mb=free_mb)
        self._save_paused()

    def resume_ingest(self, why: str, free_mb: Optional[int] = None) -> None:
        keep = []
        for entry in self.paused:
            if self._still_ours(entry):
                self.sys.send(int(entry["pid"]), signal.SIGCONT)
                self.emit("ingest_resumed", pid=entry["pid"], why=why, free_mb=free_mb)
        self.paused = keep
        self._save_paused()

    def shutdown(self) -> None:
        """Never leave a process stopped when the monitor goes away."""
        if self.paused:
            self.resume_ingest("monitor_exit")

    # one tick
    def sample(self) -> Sample:
        procs = self.sys.ps()
        me = os.getpid()
        groups: Dict[str, List[int]] = {FINETUNE: [], EVAL: [], BAKEOFF: []}
        for pid, cmd in procs:
            if pid == me:
                continue
            kind = classify(cmd, self.bake_re)
            if kind in groups:
                groups[kind].append(pid)
        server, slots_ok, decoded = probe_server(self.sys, self.cfg.llama_url)
        return Sample(
            now=self.sys.now(), free_mb=self.sys.free_mb(), finetune_pids=groups[FINETUNE],
            eval_pids=groups[EVAL], bakeoff_pids=groups[BAKEOFF], server=server, slots_ok=slots_ok,
            decoded=decoded, gpu=self.sys.gpu_line(),
        )

    def tick(self) -> Sample:
        s = self.sample()
        procs = self.sys.ps() if s.free_mb < self.cfg.free_low_mb else []
        for kind, fields in step(self.state, self.cfg, s):
            if kind == "pause_ingest":
                self.pause_ingest(procs, fields["free_mb"])
                self.emit("low_memory", free_mb=fields["free_mb"])
            elif kind == "resume_ingest":
                if self.paused:
                    self.resume_ingest("memory_ok", fields["free_mb"])
            elif kind == "stop_bakeoff":
                for pid in fields["pids"]:
                    self.sys.send(pid, signal.SIGTERM)
                self.emit("bakeoff_stopped", **fields)
            elif kind == "log":
                ev = fields.pop("event")
                self.emit(ev, **fields)
        self._write_status(s)
        return s

    def _write_status(self, s: Sample) -> None:
        legacy = (f"free_mb={s.free_mb} gpu={s.gpu} finetune={','.join(map(str, s.finetune_pids)) or 'none'} "
                  f"eval={','.join(map(str, s.eval_pids)) or 'none'} bakeoff={','.join(map(str, s.bakeoff_pids)) or 'none'} "
                  f"server={s.server} decoded={s.decoded}\n")
        doc = {
            "ts": s.now, "free_mb": s.free_mb, "gpu": s.gpu, "server": s.server, "slots_ok": s.slots_ok,
            "decoded": s.decoded, "finetune_pids": s.finetune_pids, "eval_pids": s.eval_pids,
            "bakeoff_pids": s.bakeoff_pids, "grace_left_s": max(0, round(self.state.grace_until - s.now)),
            "paused_ingest": [e["pid"] for e in self.paused],
        }
        for path, body in ((self.status_file, legacy), (self.status_json, json.dumps(doc, sort_keys=True))):
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(body)
            os.replace(tmp, path)

    def run(self, should_stop: Callable[[], bool], sleep: Callable[[float], None] = time.sleep) -> None:
        self.emit("monitor_start", cfg={k: getattr(self.cfg, k) for k in ("free_low_mb", "free_ok_mb", "kill_floor_mb",
                  "critical_mb", "window_s", "starve_tok_s", "grace_s", "llama_url")}, resumed_list=len(self.paused))
        # entries left by a crashed monitor: drop the ones that no longer exist; the normal memory rule resumes the rest
        self.paused = [e for e in self.paused if self._still_ours(e)]
        try:
            while not should_stop():
                try:
                    self.tick()
                except Exception as exc:  # noqa: BLE001 - a monitor must survive a bad sample
                    self.emit("tick_error", error=f"{type(exc).__name__}: {exc}")
                sleep(self.cfg.tick_s)
        finally:
            self.shutdown()
            self.emit("monitor_stop")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", default=os.environ.get("BALANCE_DIR") or str(Path.home() / ".local/share/aoep-train"))
    ap.add_argument("--once", action="store_true", help="take one sample, act, write status, exit (also resumes anything it stopped)")
    args = ap.parse_args(argv)
    cfg = Config.from_env()
    mon = Monitor(System(), cfg, Path(args.dir))
    stop = {"flag": False}

    def _stop(_sig: int, _frm: Any) -> None:
        stop["flag"] = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    if args.once:
        mon.tick()  # acts once; anything it stopped stays in balance.paused.json for the next run to resume
        return 0
    atexit.register(mon.shutdown)
    mon.run(lambda: stop["flag"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
