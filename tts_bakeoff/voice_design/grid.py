"""The design bake-off: the same sentences in every demo language for a grid of stock voices x tones, as a run folder the Listening Lab loads.

Layout (same as the clone and edge runs): OUT/<model>/<lang>/<id>.wav + manifest.jsonl + meta.json per model folder, where
  voxcpm2-design~<voice>            is the neutral voice (kind plain, badge 'VoxCPM2 designed'), and
  voxcpm2-design~<voice>~<tone>     is a tone variant (kind style, nested under its voice in the lab: the Voice type filter works).
Every voice is frozen first (design once, clone from the frozen reference), so a re-run, another language or another machine gives the same voice.
Existing good clips are skipped. Put the edge-tts run of the same languages in the same folder (or serve both) for head-to-head listening.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from tts_bakeoff.build_sentences import load

from . import design, registry
from .prompt import TONES

DEMO_LANGS = ["en", "es", "zh", "yue", "vi", "th", "km", "sw", "hi"]
SMALL = {"voices": ["stock-f-young-warm", "stock-m-adult-deep"], "langs": ["en", "es", "km"], "tones": [registry.NEUTRAL]}


def model_id(voice_id: str) -> str:
    return f"voxcpm2-design~{voice_id}"


def plan(voices: list[str], tones: list[str], langs: list[str], path: Path = registry.STOCK) -> list[tuple[str, str, str]]:
    """[(base voice, tone, lang)] in a stable order; unknown voices/tones raise before any GPU time is spent."""
    out = []
    for base in voices:
        entry = registry.get(base, path)
        for tone in tones:
            if tone != registry.NEUTRAL and tone not in entry.get("tones", []):
                raise registry.StockError(f"{base} has no tone {tone!r}")
            out.extend((base, tone, lang) for lang in langs)
    return out


def write_meta(out: Path, base: str, tone: str, entry: dict, frozen: dict) -> Path:
    vid = registry.variant_id(base, tone)
    mid = model_id(vid)
    root = out / mid
    root.mkdir(parents=True, exist_ok=True)
    meta = {
        "model": mid, "designed": True, "ai_generated": True, "base_model": "voxcpm2", "adapter": "voxcpm2", "stock": base, "tone": tone,
        "gender": "Female" if entry["g"] == "f" else "Male", "age": entry["age"], "timbre": entry["timbre"], "description": frozen["description"],
        "seed": frozen["seed"], "frozen_sha256": frozen["sha256"], "ai_label": registry.AI_LABEL, "license": registry.LICENSE_NOTE,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if tone == registry.NEUTRAL:
        meta.update(kind="plain", label=f"{entry['label']} · designed")
    else:
        meta.update(kind="style", style=tone, voice=model_id(base), label=f"{entry['label']} · {tone}")
    (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (root / "scores.jsonl").touch()
    (root / "manifest.jsonl").touch()
    return root


def run(out: Path, voices: list[str], tones: list[str], langs: list[str], limit: int | None = 3, freeze_missing: bool = True, takes: int = 3,
        assets: Path | None = None, adapter_factory=None, freezer=None, log=print, path: Path = registry.STOCK) -> dict:
    """Render the grid. adapter_factory(voice_id) -> adapter and freezer(voice_id, assets) are injectable so tests need no model."""
    from tts_bakeoff.voice_clone import runner

    out = Path(out)
    stats = {"ok": 0, "failed": 0, "skipped_existing": 0, "skipped_unsupported": 0, "voices": 0}
    units = plan(voices, tones, langs, path)
    freeze = freezer or (lambda vid, root: design.freeze(vid, root, takes=takes, log=log, path=path))
    build = adapter_factory or (lambda vid: design.build_adapter(vid, assets))
    by_voice: dict[str, list[str]] = {}
    for base, tone, lang in units:
        by_voice.setdefault(registry.variant_id(base, tone), []).append(lang)
    for vid, vlangs in by_voice.items():
        base, tone = registry.split_id(vid)
        entry = registry.get(base, path)
        if registry.frozen_meta(vid, assets) is None:
            if not freeze_missing:
                log(f"{vid}: not frozen, skipped (run `freeze` or pass --freeze-missing)")
                stats["failed"] += len(vlangs)
                continue
            freeze(vid, assets)
        frozen = registry.frozen_meta(vid, assets)
        if frozen is None:
            stats["failed"] += len(vlangs)
            continue
        root = write_meta(out, base, tone, entry, frozen)
        adapter = build(vid)
        stats["voices"] += 1
        existing = runner.manifest_rows(root)
        for lang in vlangs:
            if getattr(adapter, "languages", None) and lang not in adapter.languages:
                stats["skipped_unsupported"] += 1
                continue
            for item in load(lang, limit):
                wav = root / lang / f"{item['id']}.wav"
                rel = wav.relative_to(out).as_posix()
                if runner.clip_done(out, existing.get(rel)):
                    stats["skipped_existing"] += 1
                    continue
                row = {"model": root.name, "lang": lang, "id": item["id"], "text": item["text"], "wav": rel, "designed": True}
                try:
                    info = adapter.synthesize(item["text"], lang, wav)
                    row.update(status="ok", **{k: info[k] for k in ("duration_s", "synth_s", "sample_rate", "rtf") if k in info})
                    stats["ok"] += 1
                    log(f"[{root.name}] {lang} {item['id']} ok")
                except Exception as exc:  # noqa: BLE001 - one bad clip must not stop the grid
                    row.update(status="failed", error=str(exc)[:200])
                    stats["failed"] += 1
                    log(f"[{root.name}] {lang} {item['id']} FAILED {str(exc)[:100]}")
                runner.append_row(root / "manifest.jsonl", row)
        design._remember_model(adapter)
    return stats
