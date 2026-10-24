"""Clone bake-off and enrollment CLI. Run on the Spark (GPU) through scripts/run_voice_clone.sh.

  python3 -m tts_bakeoff.voice_clone.bakeoff consent  --speaker alice --name "Alice Tran" --role employee --signed-form ~/Downloads/alice-signed.pdf
  python3 -m tts_bakeoff.voice_clone.bakeoff enroll   --speaker alice --audio ~/alice.m4a --transcript-file ~/alice.txt --lang en
  python3 -m tts_bakeoff.voice_clone.bakeoff run      --out runs/2026-10-25-clones [--speakers alice,bob] [--models voxcpm2,cosyvoice2] [--langs en,es,zh] [--limit 3]
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
import socket
import sys
import time
from pathlib import Path

from tts_bakeoff.build_sentences import load

from . import enroll, registry, synth, tones


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
    info = enroll.prepare(a.audio, dest)
    registry.add_sample(a.speaker, dest, text, a.lang)
    print(f"enrolled {dest.name}: {info}")
    return 0


def synthesize_all(out: Path, speakers: list[str], models: list[str], langs: list[str], limit: int | None,
                   base: Path | None = None, gpu: bool = True) -> dict:
    counts = {"ok": 0, "failed": 0, "skipped_unsupported": 0, "refused": 0}
    for speaker in speakers:
        try:
            rec = registry.require_consent(speaker, "course_narration", base)
        except registry.ConsentError as exc:
            print(f"REFUSED {speaker}: {exc}")
            counts["refused"] += 1
            continue
        for model in models:
            adapter = synth.build_adapter(model, speaker, base, gpu=gpu)
            vid = f"{model}~{speaker}"
            root = out / vid
            root.mkdir(parents=True, exist_ok=True)
            (root / "meta.json").write_text(json.dumps({
                "model": vid, "clone": True, "consented": True, "base_model": model, "speaker": speaker,
                "role": rec["role"], "consent_date": rec["date"], "host": socket.gethostname(),
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }, indent=2), encoding="utf-8")
            (root / "scores.jsonl").touch()
            with (root / "manifest.jsonl").open("a", encoding="utf-8") as mf:
                for lang in langs:
                    if not adapter.supports(lang):
                        counts["skipped_unsupported"] += 1
                        continue
                    for item in load(lang, limit):
                        wav = root / lang / f"{item['id']}.wav"
                        row = {"model": vid, "lang": lang, "id": item["id"], "text": item["text"], "wav": wav.relative_to(out).as_posix()}
                        try:
                            row.update(adapter.synthesize(item["text"], lang, wav))
                            row["status"] = "ok"
                            counts["ok"] += 1
                        except Exception as exc:  # noqa: BLE001 - record and carry on
                            row.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
                            counts["failed"] += 1
                        mf.write(json.dumps(row, ensure_ascii=False) + "\n")
                        mf.flush()
                        print(f"[{vid}] {lang} {item['id']} {row['status']}")
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("consent"); c.add_argument("--speaker", required=True); c.add_argument("--name", required=True)
    c.add_argument("--role", required=True, choices=registry.ROLES); c.add_argument("--signed-form", required=True)
    e = sub.add_parser("enroll"); e.add_argument("--speaker", required=True); e.add_argument("--audio", required=True)
    e.add_argument("--lang", required=True); e.add_argument("--transcript", default=""); e.add_argument("--transcript-file")
    r = sub.add_parser("run"); r.add_argument("--out", required=True); r.add_argument("--speakers", default="")
    r.add_argument("--models", default="voxcpm2,cosyvoice2"); r.add_argument("--langs", default="en,es,zh")
    r.add_argument("--limit", type=int, default=3); r.add_argument("--no-gpu", action="store_true", help="tests only (mock model)")
    v = sub.add_parser("revoke"); v.add_argument("--speaker", required=True)
    g = sub.add_parser("grant-scope"); g.add_argument("--speaker", required=True); g.add_argument("--signed-form", required=True)
    g.add_argument("--scope", default="stylized_versions", choices=registry.OPTIONAL_SCOPES)
    w = sub.add_parser("withdraw-scope"); w.add_argument("--speaker", required=True)
    w.add_argument("--scope", default="stylized_versions", choices=registry.OPTIONAL_SCOPES)
    t = sub.add_parser("tones"); t.add_argument("--out", required=True); t.add_argument("--speakers", default="")
    t.add_argument("--models", default="voxcpm2"); t.add_argument("--langs", default="en,es,zh")
    t.add_argument("--tones", default="all", help="comma list of neutral, presets, blends; 'all' = neutral + presets + blends; 'presets' = neutral + presets")
    t.add_argument("--mechanisms", default="dsp,model", help="dsp = post-process the neutral clone (CPU); model = ask the model for the style (one GPU synthesis per tone)")
    t.add_argument("--model-blends", action="store_true", help="also run blends through the model mechanism (22 extra GPU clips per sentence)")
    t.add_argument("--limit", type=int, default=1); t.add_argument("--no-gpu", action="store_true", help="tests only (mock model)")
    sub.add_parser("list")
    a = ap.parse_args(argv)
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
        speakers = [s for s in a.speakers.split(",") if s] or registry.list_speakers()
        if a.cmd == "tones":
            if a.tones == "all":
                names = [tones.NEUTRAL, *tones.PRESET_NAMES, *tones.BLEND_NAMES]
            elif a.tones == "presets":
                names = [tones.NEUTRAL, *tones.PRESET_NAMES]
            else:
                names = [x for x in a.tones.split(",") if x]
            counts = tones.run_tones(Path(a.out), speakers, a.models.split(","), a.langs.split(","), names, a.mechanisms.split(","),
                                     a.limit, gpu=not a.no_gpu, model_blends=a.model_blends)
            print(counts)
            return 0 if counts["failed"] == 0 else 1
        counts = synthesize_all(Path(a.out), speakers, a.models.split(","), a.langs.split(","), a.limit, gpu=not a.no_gpu)
        print(counts)
        return 0 if counts["failed"] == 0 and counts["refused"] == 0 else 1
    except (registry.ConsentError, enroll.SampleError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
