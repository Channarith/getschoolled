"""Render the edge-tts listening set for every platform and extra language (the data for the listening lab).

  python3 -m tts_bakeoff.edge_all --out runs/2026-10-25-all --plan        # clip count and time estimate, nothing synthesized
  python3 -m tts_bakeoff.edge_all --out runs/2026-10-25-all [--workers 3] [--langs fr,ar]

Per language with a voice (from edge_voices.json, see edge_catalog.py):
  default female and default male .... all 10 sentences (SET10, see sentence_set.py)
  9 character presets ............... on the default female, sentences S01 and Q01 (prosody only: rate, pitch, volume)
  every other voice of the language .. one sentence, id A01 (= that language's S01 text): regional accents, extra voices
Layout: OUT/<voice or voice~preset>/<lang>/<id>.wav + manifest.jsonl + meta.json per model folder, and OUT/catalog.json
(language entries and a model index) for the lab. Resumable: finished clips are skipped, failed ones are retried. Progress goes
to OUT/progress.log. INTERNAL REFERENCE ONLY: edge-tts is an unofficial client of Microsoft's Edge Read Aloud service.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .adapters import get
from .edge_catalog import SNAPSHOT, load_voices
from .sentence_set import SET10, load10
from .voice_types import PRESETS

STYLE_IDS = ("S01", "Q01")
SEC_PER_CLIP = 3.0  # measured: about 1.5-2.5 s synthesis plus the polite delay


def short(name: str) -> str:
    return name.split("-", 2)[2].removesuffix("Neural")


def build_plan(catalog: dict, voices: list[dict], langs: set[str] | None = None) -> tuple[list[dict], dict]:
    by_name = {v["name"]: v for v in voices}
    plan, models = [], {}

    def add(model: str, code: str, voice: str, sid: str, text: str, kind: str, label: str, style: str | None = None, prosody=None):
        v = by_name[voice]
        models.setdefault(model, {"voice": voice, "lang": code, "gender": v["gender"], "locale": v["locale"], "kind": kind, "style": style,
                                  "label": label, "personalities": v["personalities"], "categories": v["categories"], "adapter": "edge_tts"})
        plan.append({"model": model, "lang": code, "id": sid, "voice": voice, "text": text, "label": label,
                     **({"rate": prosody[0], "pitch": prosody[1], "volume": prosody[2]} if prosody else {})})

    for code, e in catalog.items():
        if e["status"] != "voice" or (langs and code not in langs):
            continue
        texts = {r["id"]: r["text"] for r in load10(code)}
        defaults = [v for v in (e["default"]["female"], e["default"]["male"]) if v]
        for voice in defaults:
            g = by_name[voice]["gender"][0]
            for sid in SET10:
                add(voice, code, voice, sid, texts[sid], "default", f"{short(voice)} · {g} · {by_name[voice]['locale']}")
        base = e["default"]["female"] or e["default"]["male"]
        for preset, prosody in PRESETS.items():
            for sid in STYLE_IDS:
                add(f"{base}~{preset}", code, base, sid, texts[sid], "style", f"{short(base)} · {preset}", style=preset, prosody=prosody)
        for region in e["regions"]:
            for voice in region["voices"]:
                if voice not in defaults:
                    g = by_name[voice]["gender"][0]
                    add(voice, code, voice, "A01", texts["S01"], "regional", f"{short(voice)} · {g} · {by_name[voice]['locale']}")
    return plan, models


def wav_path(out: Path, job: dict) -> Path:
    return out / job["model"] / job["lang"] / f"{job['id']}.wav"


def write_catalog(out: Path, catalog: dict, models: dict) -> None:
    languages = [{k: e[k] for k in ("code", "name", "native", "rtl", "platform", "status", "reason", "alternative", "default", "voice_count")}
                 | {"regions": [{"locale": r["locale"], "region": r["region"]} for r in e["regions"]]} for e in catalog.values()]
    (out / "catalog.json").write_text(json.dumps({"languages": languages, "models": models}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--plan", action="store_true", help="print the plan and exit")
    ap.add_argument("--langs", help="comma separated language codes (default: all)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--log", default="progress.log", help="progress log file name inside --out (use one per process when running several)")
    ap.add_argument("--delay", type=float, default=0.5, help="seconds each worker waits between requests (the service rate-limits)")
    args = ap.parse_args(argv)
    doc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    plan, models = build_plan(doc["catalog"], load_voices())  # catalog.json always describes every model, even when --langs limits this run
    if args.langs:
        wanted = set(args.langs.split(","))
        plan = [j for j in plan if j["lang"] in wanted]
    kinds = {k: sum(1 for j in plan if models[j["model"]]["kind"] == k) for k in ("default", "style", "regional")}
    est = len(plan) * SEC_PER_CLIP / max(1, args.workers)
    print(f"{len(plan)} clips in {len(models)} model folders {kinds}; about {est / 60:.0f} min with {args.workers} workers", flush=True)
    if args.plan:
        return 0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_catalog(out, doc["catalog"], models)
    rows: dict[str, dict[tuple, dict]] = {}
    lock = threading.Lock()
    stats = {"ok": 0, "skipped": 0, "failed": 0}
    log = (out / args.log).open("a", encoding="utf-8")

    def flush_manifest(model: str) -> None:
        mdir = out / model
        mdir.mkdir(parents=True, exist_ok=True)
        (mdir / "manifest.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows[model].values()), encoding="utf-8")
        (mdir / "meta.json").write_text(json.dumps({"model": model, **models[model]}, ensure_ascii=False, indent=1), encoding="utf-8")

    for model in models:  # load what earlier runs finished
        mf = out / model / "manifest.jsonl"
        rows[model] = {}
        if mf.exists():
            for line in mf.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r.get("status") == "ok":
                    rows[model][(r["lang"], r["id"])] = r

    def work(job: dict) -> None:
        wav = wav_path(out, job)
        if wav.exists() and wav.stat().st_size > 2000 and (job["lang"], job["id"]) in rows[job["model"]]:
            with lock:
                stats["skipped"] += 1
            return
        opts = {k: job[k] for k in ("voice", "rate", "pitch", "volume") if k in job}
        try:
            r = get("edge_tts", **opts).synthesize(job["text"], job["lang"], wav)
            row = {"model": job["model"], "lang": job["lang"], "id": job["id"], "text": job["text"], "wav": f"{job['model']}/{job['lang']}/{job['id']}.wav",
                   "duration_s": r["duration_s"], "synth_s": r["synth_s"], "sample_rate": r["sample_rate"], "rtf": r["rtf"], "status": "ok", "label": job["label"]}
        except Exception as exc:  # noqa: BLE001
            row = {"model": job["model"], "lang": job["lang"], "id": job["id"], "text": job["text"], "status": "failed", "error": str(exc)[:160], "label": job["label"]}
        with lock:
            stats["ok" if row["status"] == "ok" else "failed"] += 1
            rows[job["model"]][(job["lang"], job["id"])] = row
            flush_manifest(job["model"])
            done = sum(stats.values())
            log.write(f"[{done}/{len(plan)}] {row['status']} {job['lang']} {job['model']} {job['id']}" + (f" {row['error']}" if row["status"] == "failed" else "") + "\n")
            log.flush()
        time.sleep(args.delay)

    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, plan))
    log.write(json.dumps({**stats, "seconds": round(time.time() - started)}) + "\n")
    log.close()
    print(json.dumps(stats))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
