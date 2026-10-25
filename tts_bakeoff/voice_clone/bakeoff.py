"""Clone bake-off and enrollment CLI. Run on the Spark (GPU) through scripts/run_voice_clone.sh.

  python3 -m tts_bakeoff.voice_clone.bakeoff consent  --speaker alice --name "Alice Tran" --role employee --signed-form ~/Downloads/alice-signed.pdf
  python3 -m tts_bakeoff.voice_clone.bakeoff enroll   --speaker alice --audio ~/alice.m4a --transcript-file ~/alice.txt --lang en
  python3 -m tts_bakeoff.voice_clone.bakeoff run      --out runs/2026-10-25-clones [--speakers alice,bob] [--models voxcpm2,cosyvoice2] [--langs en,es,zh] [--limit 3] [--takes 3] [--no-clean]
                                                  [--workers 2] [--post-threads 2] [--force] [--langs all]
  python3 -m tts_bakeoff.voice_clone.bakeoff status   --out runs/2026-10-25-clones      (read-only: progress, ETA, DONE/RUNNING)
  python3 -m tts_bakeoff.voice_clone.bakeoff say      --speaker alice --model voxcpm2 --lang en --text-file words.txt --out say/alice/one.wav
  python3 -m tts_bakeoff.voice_clone.bakeoff revoke   --speaker alice
  python3 -m tts_bakeoff.voice_clone.bakeoff grant-scope --speaker alice --signed-form alice-stylized-addendum.pdf   (CONSENT_ADDENDUM_STYLIZED.txt)
  python3 -m tts_bakeoff.voice_clone.bakeoff tones    --out runs/2026-10-25-clone-tones [--tones neutral,cute,anime,...] [--mechanisms dsp,model]
  python3 -m tts_bakeoff.voice_clone.bakeoff list

Output: OUT/<model>~<speaker>/<lang>/<id>.wav + manifest.jsonl + meta.json (clone=true, consented=true) + empty scores.jsonl,
loadable with: python3 -m tts_bakeoff.lab --out OUT
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from pathlib import Path

from . import enroll, profile, registry, runner, status, synth, tones


def cmd_consent(a) -> int:
    rec = registry.record_consent(a.speaker, a.name, a.role, a.signed_form)
    print(f"consent recorded for {rec['speaker']} ({rec['role']}), form sha256 {rec['form_sha256'][:12]}...")
    return 0


def cmd_enroll(a) -> int:
    registry.require_consent(a.speaker, "model_training")
    d = registry.speaker_dir(a.speaker)
    text = Path(a.transcript_file).read_text(encoding="utf-8") if a.transcript_file else a.transcript
    if not text or len(text.split()) < 8 and a.lang not in ("zh", "km", "th"):
        print("a transcript of exactly what was said is required (CosyVoice 2 zero-shot needs it)", file=sys.stderr)
        return 2
    dest = d / "samples" / (Path(a.audio).stem + ".wav")
    info = enroll.prepare(a.audio, dest, clean=False if a.no_clean else None)
    registry.add_sample(a.speaker, dest, text, a.lang, extra={k: info[k] for k in ("seconds", "snr_db", "cleaned", "snr_db_clean") if k in info})
    print(f"enrolled {dest.name}: {info}")
    return 0


def synthesize_all(out: Path, speakers: list[str], models: list[str], langs: list[str] | None, limit: int | None,
                   base: Path | None = None, gpu: bool = True, takes: int | None = None, clean: bool | None = None,
                   workers: int = 1, shard: tuple[int, int] | None = None, force: bool = False, post_threads: int = 2,
                   strict_workers: bool = False) -> dict:
    """The clone run (see runner.py): skips clips already done unless ``force``; ``workers`` > 1 shards the work over subprocesses.

    Returns counts: ok, failed, skipped_unsupported, refused, skipped_existing.
    """
    return runner.run_clone(out, speakers, models, langs, limit, base=base, gpu=gpu, takes=takes, clean=clean, workers=workers,
                            shard=shard, force=force, post_threads=post_threads, strict_workers=strict_workers)


def say_once(speaker: str, model: str, lang: str, text: str, out: Path, base: Path | None = None, gpu: bool = True,
             tone: str = "neutral", mechanism: str = "dsp") -> dict:
    """Speak ``text`` in an enrolled voice. Same gate as every synthesis; writes OUT plus OUT.json labelling it AI-generated.
    ``tone`` other than neutral also needs the speaker's signed stylized_versions addendum (tones.py).

    OUT.running exists while the model works, so a caller can tell "waiting for the GPU lock" from "running".
    """
    rec = registry.require_consent(speaker, "course_narration", base)
    text = " ".join(text.split())
    if not text:
        raise ValueError("nothing to say")
    tones.require_tone_consent(speaker, tone, base)
    adapter = synth.build_adapter(model, speaker, base, gpu=gpu)
    if not adapter.supports(lang):
        raise ValueError(f"{model} does not speak {lang!r}")
    out.parent.mkdir(parents=True, exist_ok=True)
    marker = out.with_suffix(".running")
    marker.touch()
    try:
        if tone == tones.NEUTRAL:
            info = adapter.synthesize(text, lang, out)
        else:
            info = tones.render_tone_clip(speaker, model, text, lang, tone, mechanism, out, base, gpu)
    finally:
        marker.unlink(missing_ok=True)
    meta = {"ai_generated": True, "label": f"AI-generated voice of {rec['name']}" + ("" if tone == tones.NEUTRAL else f" ({tone} tone)"), "speaker": speaker, "name": rec["name"], "model": model,
            "lang": lang, "text": text, "consent_date": rec["date"], "host": socket.gethostname(),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **info}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


REF_HELP = ("VoxCPM2 reference mode: continue = audio + its exact transcript (same language), reference = audio only (other languages, "
            "or a transcript that may not match); auto (default) picks per sentence. Logged per clip.")


def _langs_arg(arg: str, supported: bool = False) -> list[str] | None:
    """None = each speaker's own languages (the default); 'all' = every demo language (tones) or, with supported=True (run),
    every language the model supports; else the explicit list."""
    if not arg:
        return None
    if arg == "all":
        return list(runner.SUPPORTED) if supported else list(profile.ALL_LANGS)
    return [x for x in arg.split(",") if x]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("consent"); c.add_argument("--speaker", required=True); c.add_argument("--name", required=True)
    c.add_argument("--role", required=True, choices=registry.ROLES); c.add_argument("--signed-form", required=True)
    e = sub.add_parser("enroll"); e.add_argument("--speaker", required=True); e.add_argument("--audio", required=True)
    e.add_argument("--lang", required=True); e.add_argument("--transcript", default=""); e.add_argument("--transcript-file"); e.add_argument("--no-clean", action="store_true", help="keep the recording exactly as imported")
    r = sub.add_parser("run"); r.add_argument("--out", required=True); r.add_argument("--speakers", default="")
    r.add_argument("--models", default="voxcpm2,cosyvoice2"); r.add_argument("--langs", default="", help="comma list, or 'all' = every language the model supports; default: each speaker's own language(s) from their enrollment")
    r.add_argument("--ref-mode", choices=profile.REF_MODES, help=REF_HELP); r.add_argument("--limit", type=int, default=3); r.add_argument("--takes", type=int, default=None, help="takes per sentence, cleanest kept (default 3; 1 = single take)")
    r.add_argument("--no-clean", action="store_true", help="skip post-processing (best-of-N still applies unless --takes 1)"); r.add_argument("--no-gpu", action="store_true", help="tests only (mock model)")
    r.add_argument("--workers", type=int, default=int(os.environ.get("GS_CLONE_WORKERS") or 2), help="worker processes sharing the work under this one job (default 2, env GS_CLONE_WORKERS); reduced to what fits above the 16 GB memory gate")
    r.add_argument("--strict-workers", action="store_true", help="refuse (exit 75) instead of reducing --workers when they would not fit in memory")
    r.add_argument("--post-threads", type=int, default=int(os.environ.get("GS_CLONE_POST_THREADS") or 2), help="threads for the CPU stage (scoring, cleaning) that overlap the next synthesis")
    r.add_argument("--force", action="store_true", help="regenerate clips that already exist (default: skip finished clips)")
    r.add_argument("--shard", default="", help=argparse.SUPPRESS)
    st = sub.add_parser("status", help="read-only: what is done, what is running, ETA"); st.add_argument("--out", required=True); st.add_argument("--speakers", default="")
    st.add_argument("--models", default=""); st.add_argument("--langs", default="", help="what the run was asked for (comma list or 'all'); default: the plan the run recorded")
    st.add_argument("--limit", type=int, default=3)
    y = sub.add_parser("say"); y.add_argument("--speaker", required=True); y.add_argument("--model", required=True, choices=synth.CLONE_MODELS)
    y.add_argument("--lang", required=True); y.add_argument("--text-file", required=True); y.add_argument("--out", required=True)
    y.add_argument("--ref-mode", choices=profile.REF_MODES, help=REF_HELP)
    y.add_argument("--no-gpu", action="store_true", help="tests only (mock model)")
    y.add_argument("--tone", default="neutral", help="neutral, a preset or a blend; needs the signed stylized_versions addendum")
    y.add_argument("--mechanism", default="dsp", choices=("dsp", "model"))
    v = sub.add_parser("revoke"); v.add_argument("--speaker", required=True)
    g = sub.add_parser("grant-scope"); g.add_argument("--speaker", required=True); g.add_argument("--signed-form", required=True)
    g.add_argument("--scope", default="stylized_versions", choices=registry.OPTIONAL_SCOPES)
    w = sub.add_parser("withdraw-scope"); w.add_argument("--speaker", required=True)
    w.add_argument("--scope", default="stylized_versions", choices=registry.OPTIONAL_SCOPES)
    t = sub.add_parser("tones"); t.add_argument("--out", required=True); t.add_argument("--speakers", default="")
    t.add_argument("--models", default="voxcpm2"); t.add_argument("--langs", default="", help="comma list, or 'all'; default: each speaker's own language(s)")
    t.add_argument("--tones", default="all", help="comma list of neutral, presets, blends; 'all' = neutral + presets + blends; 'presets' = neutral + presets")
    t.add_argument("--mechanisms", default="dsp,model", help="dsp = post-process the neutral clone (CPU); model = ask the model for the style (one GPU synthesis per tone)")
    t.add_argument("--model-blends", action="store_true", help="also run blends through the model mechanism (22 extra GPU clips per sentence)")
    t.add_argument("--ref-mode", choices=profile.REF_MODES, help=REF_HELP); t.add_argument("--limit", type=int, default=1); t.add_argument("--no-gpu", action="store_true", help="tests only (mock model)")
    t.add_argument("--takes", type=int, default=None, help="takes per clip, cleanest kept (default 3)"); t.add_argument("--no-clean", action="store_true")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    if getattr(a, "ref_mode", None):
        os.environ["GS_CLONE_REF_MODE"] = a.ref_mode   # read by synth.build_adapter
    try:
        if a.cmd == "consent":
            return cmd_consent(a)
        if a.cmd == "enroll":
            return cmd_enroll(a)
        if a.cmd == "revoke":
            registry.revoke(a.speaker); print(f"consent for {a.speaker} revoked; its voice will no longer synthesize"); return 0
        if a.cmd == "list":
            for s in registry.list_speakers():
                rec = registry.load_consent(s); print(s, rec["role"], "REVOKED" if rec["revoked"] else "ok", f"{len(rec['samples'])} sample(s)")
            return 0
        if a.cmd == "grant-scope":
            rec = registry.grant_scope(a.speaker, a.scope, a.signed_form)
            print(f"{a.scope} granted to {a.speaker} (addendum sha256 {rec['scope_grants'][a.scope]['form_sha256'][:12]}...)"); return 0
        if a.cmd == "withdraw-scope":
            registry.revoke_scope(a.speaker, a.scope); print(f"{a.scope} withdrawn for {a.speaker}; natural-voice consent is unchanged"); return 0
        if a.cmd == "say":
            meta = say_once(a.speaker, a.model, a.lang, Path(a.text_file).read_text(encoding="utf-8"), Path(a.out), gpu=not a.no_gpu,
                            tone=a.tone, mechanism=a.mechanism)
            print(f"said {len(meta['text'])} characters as {meta['label']}: {a.out}")
            return 0
        if a.cmd == "status":
            return status.main(a)
        speakers = [s for s in a.speakers.split(",") if s] or registry.list_speakers()
        if a.cmd == "tones":
            if a.tones == "all":
                names = [tones.NEUTRAL, *tones.PRESET_NAMES, *tones.BLEND_NAMES]
            elif a.tones == "presets":
                names = [tones.NEUTRAL, *tones.PRESET_NAMES]
            else:
                names = [x for x in a.tones.split(",") if x]
            counts = tones.run_tones(Path(a.out), speakers, a.models.split(","), _langs_arg(a.langs), names, a.mechanisms.split(","),
                                     a.limit, gpu=not a.no_gpu, model_blends=a.model_blends, takes=a.takes,
                                     clean=False if a.no_clean else None)
            print(counts)
            return 0 if counts["failed"] == 0 else 1
        shard = tuple(int(x) for x in a.shard.split("/")) if a.shard else None
        counts = synthesize_all(Path(a.out), speakers, a.models.split(","), _langs_arg(a.langs, supported=True), a.limit, gpu=not a.no_gpu,
                                takes=a.takes, clean=False if a.no_clean else None, workers=a.workers, shard=shard, force=a.force,
                                post_threads=a.post_threads, strict_workers=a.strict_workers)
        print(counts)
        if counts.pop("refused_workers", 0):
            print("refused: not enough free memory for that many workers (--strict-workers)", file=sys.stderr)
            return 75
        return 0 if counts["failed"] == 0 and counts["refused"] == 0 else 1
    except (registry.ConsentError, enroll.SampleError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
