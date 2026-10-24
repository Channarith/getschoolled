"""Render the demo manifest in a consented company voice (run on the Spark under scripts/gs_run.sh --gpu).

  python3 -m tts_bakeoff.demo_voice.render run --voice channarith [--shard 0/2] [--langs en,es] [--limit N]
  python3 -m tts_bakeoff.demo_voice.render publish          # rewrite <assets>/voices.json + per-voice index.json
  python3 -m tts_bakeoff.demo_voice.render prune-revoked    # delete clips of any voice whose consent is gone

Assets (not in git): <assets>/<voice>/<lang>/<hash>.mp3 + <hash>.json sidecar ("AI-generated voice of <name>"),
<assets>/<voice>/index.json (hashes present, per language) and <assets>/voices.json (the selectable, consented voices).
Default assets dir: $GS_VOICE_ASSETS or ~/voice-assets. Every synthesis goes through voice_clone.synth.build_adapter,
so no valid consent (commercial use, model training, course narration; sample hashes intact) means no audio.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from tts_bakeoff.voice_clone import registry

from .manifest import MANIFEST, VOICES


def assets_dir(path: str | None = None) -> Path:
    return Path(path or os.environ.get("GS_VOICE_ASSETS") or Path.home() / "voice-assets")


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def voice_cfg(voice: str) -> dict:
    for v in json.loads(VOICES.read_text(encoding="utf-8"))["voices"]:
        if v["id"] == voice:
            return v
    raise SystemExit(f"unknown voice {voice!r}: add it to tts_manifest/voices.json")


def in_shard(h: str, shard: str | None) -> bool:
    if not shard:
        return True
    i, n = (int(x) for x in shard.split("/"))
    return int(h, 16) % n == i


def clip_path(root: Path, voice: str, lang: str, h: str, ext: str = "mp3") -> Path:
    return root / voice / lang / f"{h}.{ext}"


def wav_to_mp3(wav: Path, mp3: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to write mp3 clips")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "24000", "-b:a", "64k", str(mp3)], check=True)


def consent_ok(speaker: str) -> bool:
    try:
        registry.require_consent(speaker, "course_narration")
        return True
    except registry.ConsentError:
        return False


def publish(root: Path, manifest: dict | None = None, check_consent=consent_ok) -> dict:
    """Write voices.json (only voices whose consent is valid right now) and each voice's index.json."""
    manifest = manifest or load_manifest()
    root.mkdir(parents=True, exist_ok=True)
    out = []
    for v in manifest["voices"]:
        active = bool(v.get("active", True)) and check_consent(v["speaker"])
        index: dict[str, list[str]] = {}
        for p in sorted((root / v["id"]).glob("*/*.mp3")) if active else []:
            index.setdefault(p.parent.name, []).append(p.stem)
        if (root / v["id"]).is_dir() or active:
            (root / v["id"]).mkdir(parents=True, exist_ok=True)
            (root / v["id"] / "index.json").write_text(json.dumps({"voice": v["id"], "ext": "mp3", "clips": index}, indent=1), encoding="utf-8")
        out.append({"id": v["id"], "label": v["label"], "ai_label": v.get("ai_label", f"AI-generated voice of {v['label']}"), "active": active})
    doc = {"voices": out, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (root / "voices.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return doc


def prune_revoked(root: Path, check_consent=consent_ok) -> list[str]:
    gone = []
    for v in json.loads(VOICES.read_text(encoding="utf-8"))["voices"]:
        if not check_consent(v["speaker"]) and (root / v["id"]).is_dir():
            shutil.rmtree(root / v["id"])
            gone.append(v["id"])
    publish(root)
    return gone


def run(voice: str, root: Path, shard: str | None, langs: set[str] | None, limit: int | None, manifest: dict | None = None,
        adapter=None, convert=wav_to_mp3) -> dict:
    manifest = manifest or load_manifest()
    cfg = voice_cfg(voice)
    registry.require_consent(cfg["speaker"], "course_narration")
    if adapter is None:
        from tts_bakeoff.voice_clone.synth import build_adapter
        adapter = build_adapter(cfg["model"], cfg["speaker"])
    supported = set(getattr(adapter, "languages", set()) or set())
    stats = {"ok": 0, "skipped_existing": 0, "skipped_unsupported": 0, "failed": 0}
    todo = [c for c in manifest["clips"] if in_shard(c["hash"], shard) and (not langs or c["lang"] in langs)]
    for n, c in enumerate(todo, 1):
        if limit is not None and stats["ok"] >= limit:
            break
        mp3 = clip_path(root, voice, c["lang"], c["hash"])
        if mp3.exists() and mp3.stat().st_size > 500:
            stats["skipped_existing"] += 1
            continue
        if supported and c["lang"] not in supported:
            stats["skipped_unsupported"] += 1
            continue
        mp3.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory() as td:
                wav = Path(td) / "c.wav"
                adapter.synthesize(c["text"], c["lang"], wav)
                convert(wav, mp3)
            mp3.with_suffix(".json").write_text(json.dumps({
                "text": c["text"], "lang": c["lang"], "demo": c["demo"], "model": cfg["model"], "speaker": cfg["speaker"],
                "ai_generated": True, "label": cfg.get("ai_label", f"AI-generated voice of {cfg['label']}"),
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            stats["ok"] += 1
            print(f"[{n}/{len(todo)}] ok {c['demo']} {c['lang']} {c['hash']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            print(f"[{n}/{len(todo)}] FAILED {c['lang']} {c['hash']}: {str(exc)[:120]}", flush=True)
    publish(root, manifest)
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--voice", default="channarith")
    r.add_argument("--shard")
    r.add_argument("--langs")
    r.add_argument("--limit", type=int)
    for name in ("run", "publish", "prune-revoked"):
        (r if name == "run" else sub.add_parser(name)).add_argument("--assets")
    args = ap.parse_args(argv)
    root = assets_dir(args.assets)
    if args.cmd == "run":
        stats = run(args.voice, root, args.shard, set(args.langs.split(",")) if args.langs else None, args.limit)
        print(json.dumps(stats))
        return 0 if stats["failed"] == 0 else 1
    if args.cmd == "publish":
        print(json.dumps(publish(root), indent=1))
        return 0
    print("removed:", prune_revoked(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
