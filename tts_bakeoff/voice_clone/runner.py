"""The clone run: plan (speaker x model x language units), skip what is already done, optionally shard across worker processes.

Why it is shaped this way (measured on the Spark, 2026-10-25): a re-run used to regenerate every clip, the model was reloaded for each
speaker, and the CPU work after each take (scoring, cleaning) ran while the GPU sat idle. So:

  * a clip that exists, is not tiny and has an "ok" manifest row is skipped unless --force;
  * the loaded model is shared by every speaker in a process (profile.MODEL_CACHE);
  * synthesis is serialized (one GPU), but the CPU stage of one clip overlaps the synthesis of the next (--post-threads);
  * --workers N shards the units across N subprocesses under the ONE gs_run lock/job that started this process, each loading the model once.

Whether N > 1 is faster on the Spark's single GPU has to be measured there: scripts/measure_clone_workers.sh.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from tts_bakeoff import adapters
from tts_bakeoff.build_sentences import OUT as SENTENCES_DIR
from tts_bakeoff.build_sentences import load

from . import clean as audio_clean
from . import profile, progress, registry, synth

SUPPORTED = ["*"]   # --langs all on `run`: every language the model supports (and we have sentences for)
MODEL_MEM_GB = {"voxcpm2": 10.0, "cosyvoice2": 10.0, "mock": 0.0}   # per worker; VoxCPM2 measured ~8 GB RSS, CosyVoice 2 not measured: kept conservative
RESERVE_GB = 16.0   # the gs_run.sh start gate; workers must not eat into it


@dataclass(frozen=True)
class Unit:
    speaker: str
    model: str
    lang: str


@dataclass
class Plan:
    units: list[Unit] = field(default_factory=list)
    refused: int = 0
    unsupported: int = 0
    enrolled: dict = field(default_factory=dict)   # speaker -> (languages, display label, consent record)


def sentence_langs() -> set[str]:
    return {p.stem for p in SENTENCES_DIR.glob("*.jsonl")}


def supported_languages(model: str) -> set[str]:
    if model not in synth.CLONE_MODELS and model != "mock":
        raise registry.ConsentError(f"{model!r} is not a cloning model here; use one of {synth.CLONE_MODELS}")
    return set(adapters.get(model).languages)


def ordered_languages(supported: set[str], enrolled: list[str]) -> list[str]:
    """Own languages first, then the demo languages in their usual order, then the rest alphabetically."""
    usable = supported & sentence_langs()
    first = [l for l in [*enrolled, *profile.ALL_LANGS] if l in usable]
    return list(dict.fromkeys(first)) + sorted(usable - set(first))


def make_plan(speakers: list[str], models: list[str], langs: list[str] | None, base: Path | None = None, quiet: bool = False) -> Plan:
    plan = Plan()
    for speaker in speakers:
        try:
            rec = registry.require_consent(speaker, "course_narration", base)
        except registry.ConsentError as exc:
            if not quiet:
                print(f"REFUSED {speaker}: {exc}")
            plan.refused += 1
            continue
        enrolled = profile.speaker_languages(speaker, base) or ["en"]
        plan.enrolled[speaker] = (enrolled, profile.display_label(speaker, rec["name"], base), rec)
        for model in models:
            supported = supported_languages(model)
            wanted = ordered_languages(supported, enrolled) if langs == SUPPORTED else (langs or enrolled)
            for lang in wanted:
                if lang not in supported:
                    plan.unsupported += 1
                    continue
                plan.units.append(Unit(speaker, model, lang))
    return plan


def manifest_rows(root: Path) -> dict[str, dict]:
    """wav (relative to the run folder) -> its LAST manifest row."""
    rows: dict[str, dict] = {}
    mf = Path(root) / "manifest.jsonl"
    if mf.is_file():
        for line in mf.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("wav"):
                rows[r["wav"]] = r
    return rows


def clip_done(out: Path, row: dict | None) -> bool:
    if not row or row.get("status") != "ok":
        return False
    wav = Path(out) / row["wav"]
    return wav.is_file() and wav.stat().st_size >= progress.MIN_WAV_BYTES


def compact_manifest(root: Path) -> int:
    """Keep the last row per wav (a retried clip leaves two); returns how many rows were dropped."""
    mf = Path(root) / "manifest.jsonl"
    if not mf.is_file():
        return 0
    lines = [l for l in mf.read_text(encoding="utf-8").splitlines() if l.strip()]
    last: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        try:
            wav = json.loads(line).get("wav") or line
        except ValueError:
            wav = line
        if wav not in last:
            order.append(wav)
        last[wav] = line
    if len(order) == len(lines):
        return 0
    tmp = mf.with_name(f"manifest.jsonl.{os.getpid()}.tmp")
    tmp.write_text("\n".join(last[w] for w in order) + "\n", encoding="utf-8")
    os.replace(tmp, mf)
    return len(lines) - len(order)


def append_row(mf: Path, row: dict) -> None:
    with mf.open("a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def prepare_voice(out: Path, speaker: str, model: str, enrolled: list[str], label: str, rec: dict) -> Path:
    import socket

    vid = f"{model}~{speaker}"
    root = Path(out) / vid
    root.mkdir(parents=True, exist_ok=True)
    meta = {"model": vid, "clone": True, "consented": True, "base_model": model, "speaker": speaker, "role": rec["role"],
            "consent_date": rec["date"], "host": socket.gethostname(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "label": f"{label} · {model}", "primary_lang": enrolled[0], "langs": enrolled}
    progress.atomic_write(root / "meta.json", meta)
    (root / "scores.jsonl").touch()
    (root / "manifest.jsonl").touch()
    return root


def available_gb() -> float | None:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 1048576.0
    except OSError:
        pass
    return None


def clamp_workers(requested: int, models: list[str], avail_gb: float | None, strict: bool = False) -> tuple[int, str]:
    """The most workers whose models fit above the 16 GB gate; (n, note). strict refuses (n = 0) instead of reducing."""
    requested = max(1, requested)
    est = max([MODEL_MEM_GB.get(m, 10.0) for m in models] or [0.0])
    if avail_gb is None or est <= 0:
        return requested, ""
    fit = int((avail_gb - RESERVE_GB) // est)
    if fit >= requested:
        return requested, ""
    if strict:
        return 0, f"{requested} workers x ~{est:.0f} GB would take {avail_gb:.0f} GB below the {RESERVE_GB:.0f} GB gate (only {fit} fit)"
    n = max(1, fit)
    return n, f"workers reduced {requested} -> {n}: ~{est:.0f} GB each against {avail_gb:.0f} GB available and a {RESERVE_GB:.0f} GB gate"


def execute(out: Path, units: list[Unit], plan: Plan, limit: int | None, base: Path | None, gpu: bool, takes: int | None, clean: bool | None,
            force: bool, post_threads: int, worker: int, aggregate_each_unit: bool) -> dict:
    """Run these units in this process. The model is shared across speakers; the CPU stage of a clip overlaps the next synthesis."""
    counts = {"ok": 0, "failed": 0, "skipped_existing": 0}
    total = sum(len(load(u.lang, limit)) for u in units)
    prog = progress.WorkerProgress(out, worker, total)
    mf_locks: dict[Path, threading.Lock] = {}
    adapters_by: dict[tuple[str, str], object] = {}
    for u in units:
        enrolled, _label, _rec = plan.enrolled[u.speaker]
        key = (u.speaker, u.model)
        if key not in adapters_by:
            adapters_by[key] = synth.build_adapter(u.model, u.speaker, base, gpu=gpu)   # lazy: no model is loaded until the first clip
        adapter = adapters_by[key]
        vid = f"{u.model}~{u.speaker}"
        root = Path(out) / vid
        mf = root / "manifest.jsonl"
        lock = mf_locks.setdefault(mf, threading.Lock())
        existing = manifest_rows(root)
        prog.begin(u.speaker, u.model, u.lang)
        todo = []
        for item in load(u.lang, limit):
            wav = root / u.lang / f"{item['id']}.wav"
            rel = wav.relative_to(out).as_posix()
            if not force and clip_done(out, existing.get(rel)):
                counts["skipped_existing"] += 1
                prog.clip("skipped_existing")
                continue
            todo.append((item, wav, rel))

        def work(entry, adapter=adapter, vid=vid, mf=mf, lock=lock, lang=u.lang, speaker_enrolled=enrolled):
            item, wav, rel = entry
            row = {"model": vid, "lang": lang, "id": item["id"], "text": item["text"], "wav": rel}
            if lang not in speaker_enrolled:
                row["cross_lingual"] = True   # the lab badges these: the voice was enrolled in another language
            started = time.perf_counter()
            try:
                row.update(audio_clean.synthesize_best_of(adapter, item["text"], lang, wav, takes=takes, clean=clean))
                row["status"] = "ok"
            except Exception as exc:  # noqa: BLE001 - record and carry on
                row.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
            seconds = time.perf_counter() - started
            with lock:
                append_row(mf, row)
                counts["ok" if row["status"] == "ok" else "failed"] += 1
                prog.clip(row["status"], seconds)
                print(f"[{vid}] {lang} {item['id']} {row['status']}", flush=True)
            return row

        if todo:
            with ThreadPoolExecutor(max_workers=max(1, post_threads)) as pool:
                list(pool.map(work, todo))
        else:
            print(f"[{vid}] {u.lang}: already done, skipped", flush=True)
        if aggregate_each_unit:
            progress.aggregate(out)
    prog.finish()
    return counts


def _child_command(out: Path, speakers, models, langs, limit, takes, clean, gpu, force, post_threads, i: int, n: int) -> list[str]:
    cmd = [sys.executable, "-m", "tts_bakeoff.voice_clone.bakeoff", "run", "--out", str(out), "--speakers", ",".join(speakers),
           "--models", ",".join(models), "--limit", str(limit or 0), "--workers", "1", "--shard", f"{i}/{n}", "--post-threads", str(post_threads)]
    if langs == SUPPORTED:
        cmd += ["--langs", "all"]
    elif langs:
        cmd += ["--langs", ",".join(langs)]
    if takes is not None:
        cmd += ["--takes", str(takes)]
    if clean is False:
        cmd.append("--no-clean")
    if not gpu:
        cmd.append("--no-gpu")
    if force:
        cmd.append("--force")
    return cmd


def run_workers(out: Path, units: list[Unit], n: int, speakers, models, langs, limit, base, gpu, takes, clean, force, post_threads) -> dict:
    env = dict(os.environ)
    if base is not None:
        env["GS_VOICES_DIR"] = str(base)
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    procs = [subprocess.Popen(_child_command(out, speakers, models, langs, limit, takes, clean, gpu, force, post_threads, i, n), env=env, cwd=root)
             for i in range(n)]
    failed_procs = 0
    try:
        last = 0.0
        while any(p.poll() is None for p in procs):
            time.sleep(1.0)
            if time.time() - last > 5:
                progress.aggregate(out)
                last = time.time()
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
    for p in procs:
        if p.wait() not in (0, 1):   # 1 = some clips failed (already counted by that worker)
            failed_procs += 1
    ws = progress.read_workers(out)
    return {"ok": sum(w.get("done", 0) for w in ws), "failed": sum(w.get("failed", 0) for w in ws) + failed_procs,
            "skipped_existing": sum(w.get("skipped_existing", 0) for w in ws)}


def run_clone(out: Path, speakers: list[str], models: list[str], langs: list[str] | None, limit: int | None, base: Path | None = None,
              gpu: bool = True, takes: int | None = None, clean: bool | None = None, workers: int = 1, shard: tuple[int, int] | None = None,
              force: bool = False, post_threads: int = 2, strict_workers: bool = False) -> dict:
    out = Path(out)
    plan = make_plan(speakers, models, langs, base, quiet=bool(shard and shard[0] != 0))
    counts = {"ok": 0, "failed": 0, "skipped_unsupported": plan.unsupported, "refused": plan.refused, "skipped_existing": 0}
    units = plan.units
    if shard:
        units = units[shard[0]::shard[1]]
    else:
        for speaker, (enrolled, label, rec) in plan.enrolled.items():
            for model in models:
                prepare_voice(out, speaker, model, enrolled, label, rec)
        progress.write_plan(out, [{"speaker": u.speaker, "model": u.model, "lang": u.lang, "total": len(load(u.lang, limit))} for u in plan.units],
                            max(1, workers))
    if not units:
        if not shard:
            progress.aggregate(out)
        return counts
    if not shard and workers > 1:
        n, note = clamp_workers(min(workers, len(units)), models, available_gb(), strict_workers)
        if note:
            print(note, flush=True)
        if n == 0:
            counts["refused_workers"] = 1
            return counts
        if n > 1:
            print(f"running {len(units)} units on {n} workers", flush=True)
            done = run_workers(out, units, n, speakers, models, langs, limit, base, gpu, takes, clean, force, post_threads)
            for k, v in done.items():
                counts[k] += v
            for speaker, (_e, _l, _r) in plan.enrolled.items():
                for model in models:
                    compact_manifest(out / f"{model}~{speaker}")
            progress.aggregate(out)
            return counts
    done = execute(out, units, plan, limit, base, gpu, takes, clean, force, post_threads, shard[0] if shard else 0, aggregate_each_unit=not shard)
    for k, v in done.items():
        counts[k] += v
    if not shard:
        for speaker in plan.enrolled:
            for model in models:
                compact_manifest(out / f"{model}~{speaker}")
        progress.aggregate(out)
    return counts
