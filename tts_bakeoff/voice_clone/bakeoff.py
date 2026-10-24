"""Clone bake-off and enrollment CLI. Run on the Spark (GPU) through scripts/run_voice_clone.sh.

  python3 -m tts_bakeoff.voice_clone.bakeoff consent  --speaker alice --name "Alice Tran" --role employee --signed-form ~/Downloads/alice-signed.pdf
  python3 -m tts_bakeoff.voice_clone.bakeoff enroll   --speaker alice --audio ~/alice.m4a --transcript-file ~/alice.txt --lang en
  python3 -m tts_bakeoff.voice_clone.bakeoff run      --out runs/2026-10-25-clones [--speakers alice,bob] [--models voxcpm2,cosyvoice2] [--langs en,es,zh] [--limit 3]
  python3 -m tts_bakeoff.voice_clone.bakeoff say      --speaker alice --model voxcpm2 --lang en --text-file words.txt --out say/alice/one.wav
  python3 -m tts_bakeoff.voice_clone.bakeoff revoke   --speaker alice
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

from . import enroll, registry, synth


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


def say_once(speaker: str, model: str, lang: str, text: str, out: Path, base: Path | None = None, gpu: bool = True) -> dict:
    """Speak ``text`` in an enrolled voice. Same gate as every synthesis; writes OUT plus OUT.json labelling it AI-generated.

    OUT.running exists while the model works, so a caller can tell "waiting for the GPU lock" from "running".
    """
    rec = registry.require_consent(speaker, "course_narration", base)
    text = " ".join(text.split())
    if not text:
        raise ValueError("nothing to say")
    adapter = synth.build_adapter(model, speaker, base, gpu=gpu)
    if not adapter.supports(lang):
        raise ValueError(f"{model} does not speak {lang!r}")
    out.parent.mkdir(parents=True, exist_ok=True)
    marker = out.with_suffix(".running")
    marker.touch()
    try:
        info = adapter.synthesize(text, lang, out)
    finally:
        marker.unlink(missing_ok=True)
    meta = {"ai_generated": True, "label": f"AI-generated voice of {rec['name']}", "speaker": speaker, "name": rec["name"], "model": model,
            "lang": lang, "text": text, "consent_date": rec["date"], "host": socket.gethostname(),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **info}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


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
    y = sub.add_parser("say"); y.add_argument("--speaker", required=True); y.add_argument("--model", required=True, choices=synth.CLONE_MODELS)
    y.add_argument("--lang", required=True); y.add_argument("--text-file", required=True); y.add_argument("--out", required=True)
    y.add_argument("--no-gpu", action="store_true", help="tests only (mock model)")
    v = sub.add_parser("revoke"); v.add_argument("--speaker", required=True)
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
        if a.cmd == "say":
            meta = say_once(a.speaker, a.model, a.lang, Path(a.text_file).read_text(encoding="utf-8"), Path(a.out), gpu=not a.no_gpu)
            print(f"said {len(meta['text'])} characters as {meta['label']}: {a.out}")
            return 0
        speakers = [s for s in a.speakers.split(",") if s] or registry.list_speakers()
        counts = synthesize_all(Path(a.out), speakers, a.models.split(","), a.langs.split(","), a.limit, gpu=not a.no_gpu)
        print(counts)
        return 0 if counts["failed"] == 0 and counts["refused"] == 0 else 1
    except (registry.ConsentError, enroll.SampleError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
