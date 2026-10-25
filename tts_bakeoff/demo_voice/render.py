"""Render the demo manifest in a consented company voice (run on the Spark under scripts/gs_run.sh --gpu).

  python3 -m tts_bakeoff.demo_voice.render run --voice channarith|wei-miao|wei|all [--shard 0/2] [--langs en,es|all] [--limit N]
  python3 -m tts_bakeoff.demo_voice.render publish [--reviewed-only]   # rewrite <assets>/voices.json + per-voice index.json
  python3 -m tts_bakeoff.demo_voice.render status           # clips present per voice and language, against the manifest
  python3 -m tts_bakeoff.demo_voice.render prune-revoked    # delete clips of any voice whose consent is gone

Assets (not in git): <assets>/<voice>/<lang>/<hash>.mp3 + <hash>.json sidecar ("AI-generated voice of <name>"),
<assets>/<voice>/index.json (hashes present, per language) and <assets>/voices.json (the selectable, consented voices).
Default assets dir: $GS_VOICE_ASSETS or ~/voice-assets. Every synthesis goes through voice_clone.synth.build_adapter,
so no valid consent (commercial use, model training, course narration; sample hashes intact) means no audio.
Each voice speaks its OWN language(s) by default: the languages it was enrolled in (voice_clone.profile.speaker_languages), so the
Cantonese voice (wei) renders Cantonese and the English voices render English; --langs a,b overrides and --langs all renders every
manifest language (cross-lingual clones, quality varies). A voice's "primary_lang" in tts_manifest/voices.json renders first. Clips of machine-translated lines carry "translation_status" in their sidecar; publish --reviewed-only leaves the
'unreviewed' ones out of index.json, so only lines a native speaker has checked are offered to the demos.
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
from tts_bakeoff.voice_clone.profile import language_name, speaker_languages

from .manifest import MANIFEST, VOICES


def assets_dir(path: str | None = None) -> Path:
    return Path(path or os.environ.get("GS_VOICE_ASSETS") or Path.home() / "voice-assets")


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def voice_cfg(voice: str) -> dict:
    base, _, tone = voice.partition("~")   # 'stock-f-young-warm~professional': a tone variant of a stock voice
    for v in json.loads(VOICES.read_text(encoding="utf-8"))["voices"]:
        if v["id"] == base:
            if tone:
                if v.get("kind") != "stock":
                    raise SystemExit(f"{voice!r}: only stock voices have tone variants")
                return {**v, "id": voice, "tone": tone, "label": f"{v['label']} ({tone})"}
            return v
    raise SystemExit(f"unknown voice {voice!r}: add it to tts_manifest/voices.json")


def is_stock(cfg: dict) -> bool:
    """A designed VoxCPM2 voice: no person, so no consent record; it is gated on its frozen reference instead."""
    return cfg.get("kind") == "stock"


def stock_ready(cfg: dict, root: Path | None = None) -> bool:
    from tts_bakeoff.voice_design import registry as stock

    return stock.frozen_meta(cfg["id"], root) is not None


def in_shard(h: str, shard: str | None) -> bool:
    if not shard:
        return True
    i, n = (int(x) for x in shard.split("/"))
    return int(h, 16) % n == i


def clip_path(root: Path, voice: str, lang: str, h: str, ext: str = "mp3") -> Path:
    return root / voice / lang / f"{h}.{ext}"


def audio_ok(mp3: Path) -> bool:
    """A finished clip is a real audio file. A tiny or unreadable file is redone, not skipped."""
    if not mp3.is_file():
        return False
    try:
        if mp3.stat().st_size <= 500:
            return False
        head = mp3.read_bytes()[:4]
    except OSError:
        return False
    if head.startswith((b"ID3", b"RIFF")):
        return True
    return len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0


def sidecar_ok(mp3: Path) -> bool:
    side = mp3.with_suffix(".json")
    if not side.is_file():
        return False
    try:
        doc = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and bool(doc.get("text"))


def _discard(mp3: Path) -> None:
    mp3.unlink(missing_ok=True)
    mp3.with_suffix(".json").unlink(missing_ok=True)


def _write_sidecar(mp3: Path, cfg: dict, clip: dict, stock: bool, own: set[str] | None) -> None:
    mp3.with_suffix(".json").write_text(json.dumps({
        "text": clip["text"], "lang": clip["lang"], "demo": clip["demo"], "model": cfg["model"],
        "speaker": cfg.get("speaker") or cfg["id"],
        "ai_generated": True, "label": cfg.get("ai_label", f"AI-generated voice of {cfg['label']}"),
        **({"designed": True, "stock": cfg["id"]} if stock else {}),
        **({"translation_status": clip["status"]} if clip.get("status") else {}),
        **({"cross_lingual": True} if own and clip["lang"] not in own else {}),
    }, ensure_ascii=False, indent=1), encoding="utf-8")


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


def display_name(speaker: str, fallback: str) -> str:
    try:
        return registry.load_consent(speaker).get("name") or fallback
    except registry.ConsentError:
        return fallback


def _unreviewed(mp3: Path) -> bool:
    side = mp3.with_suffix(".json")
    if not side.is_file():
        return False
    try:
        return json.loads(side.read_text(encoding="utf-8")).get("translation_status") == "unreviewed"
    except ValueError:
        return False


def _cleared_langs(cfg: dict) -> set[str]:
    """The languages a designed voice may be published in (tts_manifest/stock_voices.json 'langs'). An unknown voice publishes nothing."""
    from tts_bakeoff.voice_design import registry as stock

    try:
        return set(stock.get(stock.split_id(cfg["id"])[0]).get("langs") or [])
    except stock.StockError:
        return set()


def publish(root: Path, manifest: dict | None = None, check_consent=consent_ok, reviewed_only: bool = False) -> dict:
    """Write voices.json (only voices whose consent is valid right now) and each voice's index.json."""
    manifest = manifest or load_manifest()
    root.mkdir(parents=True, exist_ok=True)
    out = []
    for v in manifest["voices"]:
        stock = is_stock(v)
        active = bool(v.get("active", True)) and (stock_ready(v, root) if stock else check_consent(v["speaker"]))
        index: dict[str, list[str]] = {}
        cleared_langs = _cleared_langs(v) if stock else None
        for p in sorted((root / v["id"]).glob("*/*.mp3")) if active else []:
            if reviewed_only and _unreviewed(p):
                continue
            if cleared_langs is not None and p.parent.name not in cleared_langs:
                continue   # a designed voice is only published in the languages a native speaker has listened to
            index.setdefault(p.parent.name, []).append(p.stem)
        if (root / v["id"]).is_dir() or active:
            (root / v["id"]).mkdir(parents=True, exist_ok=True)
            (root / v["id"] / "index.json").write_text(json.dumps({"voice": v["id"], "ext": "mp3", "clips": index}, indent=1), encoding="utf-8")
        label = display_name(v["speaker"], v["label"]) if (active and not stock) else v["label"]
        shown = (f"{label} (designed)" if stock else f"{label} ({language_name(v['primary_lang'])})" if v.get("primary_lang") else label)   # 'Wei (Cantonese)', 'Wei Miao (English)', 'Sage (designed)'
        entry = {"id": v["id"], "label": shown, "ai_label": v.get("ai_label", f"AI-generated voice of {label}"), "active": active}
        if v.get("primary_lang"):
            entry["primary_lang"] = v["primary_lang"]
        if v.get("gender") in ("male", "female"):
            entry["gender"] = v["gender"]   # the pages fall back to an edge voice of this gender when a clip is missing
        entry["name"] = v["label"]          # the bare name ("Sage"): the picker writes "Salane Voice (Sage)" for the default
        if stock:
            entry["kind"] = "stock"
        if v.get("default") and active:
            entry["default"] = True         # the Salane Voice for visitors who never chose one (exactly one voice carries it)
        out.append(entry)
    defaults = [e["id"] for e in out if e.get("default")]
    if len(defaults) > 1:
        for e in out:
            if e["id"] in defaults[1:]:
                e.pop("default", None)      # a second default would make the choice depend on list order: keep the first
    doc = {"voices": out, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (root / "voices.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return doc


def prune_revoked(root: Path, check_consent=consent_ok) -> list[str]:
    gone = []
    for v in json.loads(VOICES.read_text(encoding="utf-8"))["voices"]:
        if is_stock(v):
            continue   # a designed voice has no consent to lose
        if not check_consent(v["speaker"]) and (root / v["id"]).is_dir():
            shutil.rmtree(root / v["id"])
            gone.append(v["id"])
    publish(root)
    return gone


def run(voice: str, root: Path, shard: str | None, langs: set[str] | None, limit: int | None, manifest: dict | None = None,
        adapter=None, convert=wav_to_mp3, reviewed_only: bool = False, own: set[str] | None = None) -> dict:
    manifest = manifest or load_manifest()
    cfg = voice_cfg(voice)
    stock = is_stock(cfg)
    if stock:
        if not stock_ready(cfg, root):
            raise SystemExit(f"{voice}: no frozen reference yet (python3 -m tts_bakeoff.voice_design freeze --voices {voice})")
    else:
        registry.require_consent(cfg["speaker"], "course_narration")
    built_here = adapter is None
    if adapter is None:
        if stock:
            from tts_bakeoff.voice_design.design import build_adapter as build_stock

            adapter = build_stock(cfg["id"], root)
        else:
            from tts_bakeoff.voice_clone.synth import build_adapter
            adapter = build_adapter(cfg["model"], cfg["speaker"])
    supported = set(getattr(adapter, "languages", set()) or set())
    by_lang: dict[str, object] = {}   # stock voices: the adapter for a language whose cleared method uses the Cantonese-designed reference
    stats = {"ok": 0, "skipped_existing": 0, "skipped_unsupported": 0, "failed": 0}
    todo = [c for c in manifest["clips"] if in_shard(c["hash"], shard) and (not langs or c["lang"] in langs)]
    primary = cfg.get("primary_lang")
    if primary:
        todo.sort(key=lambda c: c["lang"] != primary)   # stable: the voice's own language first, then the cross-lingual clones
    for n, c in enumerate(todo, 1):
        if limit is not None and stats["ok"] >= limit:
            break
        mp3 = clip_path(root, voice, c["lang"], c["hash"])
        if audio_ok(mp3):
            if not sidecar_ok(mp3):
                _write_sidecar(mp3, cfg, c, stock, own)
            stats["skipped_existing"] += 1
            continue
        if supported and c["lang"] not in supported:
            stats["skipped_unsupported"] += 1
            continue
        _discard(mp3)
        mp3.parent.mkdir(parents=True, exist_ok=True)
        ad = adapter
        if stock and built_here:
            from tts_bakeoff.voice_design import registry as stock_registry
            from tts_bakeoff.voice_design.design import build_adapter as build_stock

            if stock_registry.reference_id(cfg["id"], c["lang"], root=root) != cfg["id"]:
                ad = by_lang.get(c["lang"]) or by_lang.setdefault(c["lang"], build_stock(cfg["id"], root, lang=c["lang"]))
        try:
            with tempfile.TemporaryDirectory() as td:
                wav = Path(td) / "c.wav"
                ad.synthesize(c["text"], c["lang"], wav)
                convert(wav, mp3)
            if not audio_ok(mp3):
                _discard(mp3)
                raise RuntimeError(f"clip {c['hash']} is not playable audio")
            _write_sidecar(mp3, cfg, c, stock, own)
            stats["ok"] += 1
            print(f"[{n}/{len(todo)}] ok {c['demo']} {c['lang']} {c['hash']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            if mp3.exists() and not audio_ok(mp3):
                _discard(mp3)
            print(f"[{n}/{len(todo)}] FAILED {c['lang']} {c['hash']}: {str(exc)[:120]}", flush=True)
    publish(root, manifest, reviewed_only=reviewed_only)
    return stats


def own_langs(cfg: dict) -> set[str]:
    """The languages this voice was enrolled in (falls back to the voice's primary_lang, then English). A stock voice has no enrolment: its
    cleared languages come from tts_manifest/stock_voices.json ('langs')."""
    if is_stock(cfg):
        from tts_bakeoff.voice_design import registry as stock

        return set(stock.get(stock.split_id(cfg["id"])[0]).get("langs") or [cfg.get("primary_lang", "en")])
    try:
        langs = speaker_languages(cfg["speaker"])
    except registry.ConsentError:
        langs = []
    return set(langs) or {cfg.get("primary_lang", "en")}


def status(root: Path, manifest: dict | None = None) -> dict:
    """{voice: {lang: [present, wanted]}} against the manifest (clips of unsupported languages still count as wanted)."""
    manifest = manifest or load_manifest()
    want: dict[str, int] = {}
    for c in manifest["clips"]:
        want[c["lang"]] = want.get(c["lang"], 0) + 1
    out = {}
    for v in manifest["voices"]:
        have = {p.name: len(list(p.glob("*.mp3"))) for p in sorted((root / v["id"]).glob("*")) if p.is_dir()}
        out[v["id"]] = {lang: [have.get(lang, 0), n] for lang, n in sorted(want.items())}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--voice", default="channarith", help="a voice id from tts_manifest/voices.json, or 'all' (every active voice, one after the other)")
    r.add_argument("--reviewed-only", action="store_true")
    r.add_argument("--ref-mode", choices=("auto", "continue", "reference"), help="VoxCPM2 reference mode (default auto: continue only for a same-language reference with an exact transcript)")
    r.add_argument("--shard")
    r.add_argument("--langs", help="comma list, or 'all' (every manifest language); default: the languages the voice was enrolled in")
    r.add_argument("--limit", type=int)
    pub = sub.add_parser("publish")
    pub.add_argument("--reviewed-only", action="store_true")
    for sp in (r, pub, sub.add_parser("prune-revoked"), sub.add_parser("status")):
        sp.add_argument("--assets")
    args = ap.parse_args(argv)
    root = assets_dir(args.assets)
    if getattr(args, "ref_mode", None):
        os.environ["GS_CLONE_REF_MODE"] = args.ref_mode
    if args.cmd == "run":
        voices = [v["id"] for v in json.loads(VOICES.read_text(encoding="utf-8"))["voices"] if v.get("active", True)] if args.voice == "all" else [args.voice]
        bad = 0
        for voice in voices:
            cfg = voice_cfg(voice)
            if (not stock_ready(cfg, root)) if is_stock(cfg) else (not consent_ok(cfg["speaker"])):
                print(f"{voice}: {'no frozen reference yet' if is_stock(cfg) else 'no valid consent right now'}, skipped", flush=True)
                bad += args.voice != "all"
                continue
            langs = None if args.langs == "all" else set(args.langs.split(",")) if args.langs else own_langs(cfg)
            print(f"{voice}: languages {'all' if langs is None else ','.join(sorted(langs))}", flush=True)
            stats = run(voice, root, args.shard, langs, args.limit, reviewed_only=args.reviewed_only, own=None if is_stock(cfg) else own_langs(cfg))
            print(voice, json.dumps(stats), flush=True)
            bad += stats["failed"] > 0
        return 0 if bad == 0 else 1
    if args.cmd == "publish":
        print(json.dumps(publish(root, reviewed_only=args.reviewed_only), indent=1))
        return 0
    if args.cmd == "status":
        for voice, langs in status(root).items():
            print(voice + ": " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in langs.items()))
        return 0
    print("removed:", prune_revoked(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
