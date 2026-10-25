"""Concurrent, resumable renderer for the pre-rendered edge-tts demo clips (plan in edge_plan.py).

  python3 -m tts_bakeoff.demo_voice.edge_render plan   [--tiers 1,2]
  python3 -m tts_bakeoff.demo_voice.edge_render run    --tiers 1 [--workers 16] [--out ~/edge-assets] [--limit N]
  python3 -m tts_bakeoff.demo_voice.edge_render status [--tiers 1,2]          # read-only: done/total per tier, rate, ETA, failures
  python3 -m tts_bakeoff.demo_voice.edge_render bench  [--sample 100]         # clips/s at 2/4/8/16 workers, throttling counts
  python3 -m tts_bakeoff.demo_voice.edge_render index  [--out ...]            # per-voice index.json + edge.json for the web client
  python3 -m tts_bakeoff.demo_voice.edge_render verify --tiers 1              # every planned clip present and non-trivial

Needs edge-tts >= 7.3.1 (Microsoft refuses older clients with 403) in the interpreter that runs it; no GPU, no API key. Clips are written
atomically and an existing clip is never re-rendered (the name is the content hash), so a stopped run resumes where it stopped.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from . import edge_plan as plan

MIN_BYTES = 800
PER_VOICE = 6
PROGRESS = "edge-progress.json"
CATALOG = "edge.json"


def assets_root(path: str | None = None) -> Path:
    return Path(path or os.environ.get("GS_EDGE_ASSETS") or Path.home() / "edge-assets")


def clip_file(root: Path, it: plan.Item) -> Path:
    return root / it.rel


def present(root: Path, it: plan.Item) -> bool:
    p = clip_file(root, it)
    return p.is_file() and p.stat().st_size >= MIN_BYTES


def parse_tiers(s: str | None) -> tuple[int, ...]:
    return tuple(int(x) for x in (s or "1,2,3,4").split(",") if x.strip())


def _is_throttle(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc} {getattr(exc, 'status', '')}"
    return any(k in text for k in ("403", "429", "Too Many", "Forbidden"))


class Stats:
    def __init__(self, total: int):
        self.total = total
        self.done = self.skipped = self.failed = self.throttled = self.retries = 0
        self.bytes = 0
        self.t0 = time.time()
        self.errors: Counter = Counter()
        self.pause_until = 0.0
        self.pause_s = 1.0

    def snapshot(self, tiers=None) -> dict:
        el = max(time.time() - self.t0, 1e-6)
        finished = self.done + self.skipped
        rate = self.done / el
        left = max(self.total - finished - self.failed, 0)
        return {"total": self.total, "done": self.done, "skipped_existing": self.skipped, "failed": self.failed,
                "throttled": self.throttled, "retries": self.retries, "bytes": self.bytes, "elapsed_s": round(el, 1),
                "rate_per_s": round(rate, 3), "eta_s": round(left / rate) if rate > 0 else None,
                "errors": dict(self.errors.most_common(6)), "updated": time.strftime("%Y-%m-%dT%H:%M:%S"), "tiers": tiers}


async def synth(text: str, voice: str, tone: str, timeout: float = 60.0) -> bytes:
    import edge_tts

    comm = edge_tts.Communicate(text, voice, **plan.prosody(tone))

    async def collect() -> bytes:
        buf = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        return bytes(buf)

    data = await asyncio.wait_for(collect(), timeout)
    if len(data) < MIN_BYTES:
        raise RuntimeError(f"audio too short ({len(data)} bytes)")
    return data


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


async def run_items(items: list[plan.Item], root: Path, workers: int = 6, attempts: int = 4, synth_fn=synth, progress_every: float = 5.0,
                    log=print, tiers=None, sleep=asyncio.sleep) -> tuple[Stats, list[plan.Item]]:
    stats = Stats(len(items))
    todo = []
    for it in items:
        if present(root, it):
            stats.skipped += 1
        else:
            todo.append(it)
    queue: asyncio.Queue = asyncio.Queue()
    for it in todo:
        queue.put_nowait(it)
    voice_sems: dict[str, asyncio.Semaphore] = {}
    failed: list[plan.Item] = []
    stop = asyncio.Event()

    async def worker() -> None:
        while not stop.is_set():
            try:
                it = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            sem = voice_sems.setdefault(it.edge, asyncio.Semaphore(PER_VOICE))
            ok = False
            for attempt in range(attempts):
                wait = stats.pause_until - time.time()
                if wait > 0:
                    await sleep(wait)
                try:
                    async with sem:
                        data = await synth_fn(it.text, it.edge, it.tone)
                    write_atomic(clip_file(root, it), data)
                    stats.done += 1
                    stats.bytes += len(data)
                    stats.pause_s = max(1.0, stats.pause_s * 0.9)
                    ok = True
                    break
                except Exception as exc:  # noqa: BLE001 - every failure mode of the service is retried the same way
                    stats.errors[type(exc).__name__] += 1
                    stats.retries += 1
                    if _is_throttle(exc):
                        stats.throttled += 1
                        stats.pause_s = min(stats.pause_s * 2, 60.0)
                        stats.pause_until = max(stats.pause_until, time.time() + stats.pause_s)
                    await sleep(min(2 ** attempt, 20) + random.random())
            if not ok:
                stats.failed += 1
                failed.append(it)

    async def reporter() -> None:
        while not stop.is_set():
            await asyncio.sleep(progress_every)
            write_progress(root, stats, tiers)

    rep = asyncio.create_task(reporter())
    await asyncio.gather(*(worker() for _ in range(max(1, workers))))
    stop.set()
    rep.cancel()
    write_progress(root, stats, tiers)
    return stats, failed


UNAVAILABLE = "edge-unavailable.json"


async def probe_voices(items: list[plan.Item], synth_fn=synth, attempts: int = 2, concurrency: int = 6) -> dict[str, str]:
    """Voices of the plan that return no audio at all (retired or broken): {edge voice: error}. They are skipped, not retried per clip."""
    sample: dict[str, str] = {}
    for it in items:
        sample.setdefault(it.edge, it.text)
    sem = asyncio.Semaphore(concurrency)

    async def one(voice: str, text: str):
        async with sem:
            err = ""
            for _ in range(attempts):
                try:
                    await synth_fn(text, voice, plan.NEUTRAL)
                    return voice, ""
                except Exception as exc:  # noqa: BLE001
                    err = type(exc).__name__
                    await asyncio.sleep(1)
            return voice, err

    return {v: e for v, e in await asyncio.gather(*(one(v, t) for v, t in sample.items())) if e}


def write_progress(root: Path, stats: Stats, tiers=None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / PROGRESS).write_text(json.dumps(stats.snapshot(tiers), indent=1) + "\n", encoding="utf-8")


def interleave(items: list[plan.Item]) -> list[plan.Item]:
    """Order by tier, line, then tone with the voice innermost, so neighbouring clips are different voices and the per-voice limit rarely queues."""
    return sorted(items, key=lambda it: (it.tier, it.demo, it.lang, it.hash, it.tone, it.edge))


def index_variants(root: Path) -> dict:
    """Write <variant>/index.json (hashes present per language) and the edge.json catalog the web picker reads."""
    voices = {v.edge: v for vs in plan.catalog_voices().values() for v in vs}
    catalog: dict = {"version": 1, "ext": "mp3", "tones": [plan.NEUTRAL, *plan.TONES], "voices": {}, "by_catalog_id": {}}
    for vdir in sorted(p for p in root.glob("edge.*") if p.is_dir()):
        base, _, tone = vdir.name[len("edge."):].partition("~")
        tone = tone or plan.NEUTRAL
        clips: dict[str, list[str]] = {}
        for ldir in sorted(p for p in vdir.iterdir() if p.is_dir()):
            hashes = sorted(f.stem for f in ldir.glob("*.mp3") if f.stat().st_size >= MIN_BYTES)
            if hashes:
                clips[ldir.name] = hashes
        (vdir / "index.json").write_text(json.dumps({"ext": "mp3", "clips": clips}, separators=(",", ":")) + "\n", encoding="utf-8")
        v = voices.get(base)
        entry = catalog["voices"].setdefault(base, {"gender": v.gender if v else "", "lang": v.lang if v else "", "label": v.label if v else base,
                                                    "tones": {}})
        entry["tones"][tone] = sorted(clips)
        if v:
            for cid in v.catalog_ids:
                catalog["by_catalog_id"][cid] = base
    (root / CATALOG).write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"variants": sum(len(v["tones"]) for v in catalog["voices"].values()), "voices": len(catalog["voices"])}


def status(items: list[plan.Item], root: Path) -> dict:
    per: dict[int, list[int]] = {}
    dead_file = root / UNAVAILABLE
    dead = set(json.loads(dead_file.read_text(encoding="utf-8"))) if dead_file.is_file() else set()   # retired voices are not counted
    for it in items:
        if it.edge in dead:
            continue
        d = per.setdefault(it.tier, [0, 0])
        d[1] += 1
        d[0] += 1 if present(root, it) else 0
    prog = {}
    pf = root / PROGRESS
    if pf.is_file():
        try:
            prog = json.loads(pf.read_text(encoding="utf-8"))
        except ValueError:
            prog = {}
    return {"tiers": per, "progress": prog}


def print_status(st: dict, out=print) -> None:
    for tier, (done, total) in sorted(st["tiers"].items()):
        pct = 100.0 * done / total if total else 100.0
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        out(f"tier {tier}: [{bar}] {done}/{total} ({pct:.1f}%)")
    p = st["progress"]
    if p:
        eta = p.get("eta_s")
        out(f"last run: {p.get('rate_per_s', 0)} clips/s, retries {p.get('retries', 0)}, throttled {p.get('throttled', 0)}, failed {p.get('failed', 0)}"
            f"{f', ETA {eta // 60} min' if eta else ''}; updated {p.get('updated', '?')}")
        if p.get("errors"):
            out(f"errors: {p['errors']}")
    total = sum(t for _, t in st["tiers"].values())
    done = sum(d for d, _ in st["tiers"].values())
    out("DONE" if total and done >= total else f"RUNNING or incomplete: {done}/{total} clips present")


async def bench(items: list[plan.Item], sample: int, levels=(2, 4, 8, 16), log=lambda m: print(m, flush=True)) -> list[dict]:
    pick = items[:]
    random.Random(7).shuffle(pick)
    pick = pick[:sample]
    rows = []
    for n in levels:
        with tempfile.TemporaryDirectory(prefix="edge-bench-") as tmp:
            t0 = time.time()
            stats, failed = await run_items(pick, Path(tmp), workers=n, attempts=2, progress_every=3600, tiers=None)
            el = time.time() - t0
            row = {"workers": n, "clips": stats.done, "failed": len(failed), "throttled": stats.throttled, "retries": stats.retries,
                   "seconds": round(el, 1), "clips_per_s": round(stats.done / el, 2), "kb_per_clip": round(stats.bytes / max(stats.done, 1) / 1024, 1)}
            rows.append(row)
            log(json.dumps(row))
        await asyncio.sleep(3)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run", "status", "verify", "bench", "index"):
        p = sub.add_parser(name)
        p.add_argument("--tiers", default="1,2,3,4")
        p.add_argument("--out")
        p.add_argument("--limit", type=int)
        p.add_argument("--workers", type=int, default=int(os.environ.get("GS_EDGE_WORKERS", "16")))
        p.add_argument("--sample", type=int, default=100)
    a = ap.parse_args(argv)
    root = assets_root(a.out)
    if a.cmd == "index":
        print(json.dumps(index_variants(root)))
        return 0
    items = interleave(plan.build(parse_tiers(a.tiers)))
    if a.limit:
        items = items[: a.limit]
    if a.cmd == "plan":
        s = plan.summarize(items)
        for tier, t in sorted(s["tiers"].items()):
            print(f"tier {tier}: {t['clips']:>7} clips, ~{t['bytes'] / 1e6:7.0f} MB; languages {t['langs']}")
        print(f"total: {s['clips']} clips, ~{s['bytes'] / 1e6:.0f} MB (estimate from text length at 48 kbit/s; the first real run replaces it)")
        return 0
    if a.cmd == "status":
        print_status(status(items, root), print)
        return 0
    if a.cmd == "verify":
        missing = [it for it in items if not present(root, it)]
        print(f"{len(items) - len(missing)}/{len(items)} clips present")
        for it in missing[:10]:
            print("missing:", it.rel)
        return 1 if missing else 0
    try:
        import edge_tts  # noqa: F401
        from importlib.metadata import version

        major_minor = tuple(int(x) for x in version("edge-tts").split(".")[:2])
        if major_minor < (7, 3):
            print(f"edge-tts {version('edge-tts')} is too old (Microsoft refuses < 7.3.1 with 403): use a venv with edge-tts>=7.3.1", file=sys.stderr)
            return 2
    except ImportError:
        print("edge-tts is not installed in this interpreter", file=sys.stderr)
        return 2
    if a.cmd == "bench":
        rows = asyncio.run(bench(items, a.sample))
        print(json.dumps(rows))
        return 0
    todo = [it for it in items if not present(root, it)]
    dead = asyncio.run(probe_voices(todo)) if todo else {}
    if dead:
        root.mkdir(parents=True, exist_ok=True)
        (root / UNAVAILABLE).write_text(json.dumps(dead, indent=1) + "\n", encoding="utf-8")
        print(f"skipping {len(dead)} voice(s) that return no audio: {dead}", flush=True)
        items = [it for it in items if it.edge not in dead]
    stats, failed = asyncio.run(run_items(items, root, workers=a.workers, tiers=list(parse_tiers(a.tiers))))
    if failed:
        print(f"retrying {len(failed)} failed clips once more with fewer workers", flush=True)
        stats2, failed = asyncio.run(run_items(failed, root, workers=max(1, a.workers // 3), attempts=6, tiers=list(parse_tiers(a.tiers))))
    print(json.dumps(stats.snapshot()))
    print(json.dumps(index_variants(root)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
