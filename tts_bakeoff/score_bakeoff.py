"""Score a bake-off run: ASR round trip + audio sanity per clip. Resumable. Runs anywhere (the Mac is fine).

  python3 -m tts_bakeoff.score_bakeoff --out runs/2026-10-24 --asr auto
  python3 -m tts_bakeoff.score_bakeoff --out /tmp/bakeoff-demo --asr fake:0.05     # no ASR model needed

Writes OUT/<model>/scores.jsonl, one row per clip. Rerunning skips clips already scored with the same ASR.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import asr as asr_mod
from .scoring import analyze_audio, error_rate


def score_model(out: Path, model: str, engine: asr_mod.ASR, naturalness: bool = False) -> dict:
    root = out / model
    manifest = root / "manifest.jsonl"
    scores_path = root / "scores.jsonl"
    done = set()
    if scores_path.exists():
        for line in scores_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("asr") == engine.name:
                    done.add((row["lang"], row["id"]))
    counts = {"scored": 0, "skipped": 0, "failed": 0}
    with scores_path.open("a", encoding="utf-8") as sf:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            m = json.loads(line)
            if m.get("status") != "ok":
                continue
            key = (m["lang"], m["id"])
            if key in done:
                counts["skipped"] += 1
                continue
            wav = out / m["wav"]
            row = {"model": model, "lang": m["lang"], "id": m["id"], "asr": engine.name, "duration_s": m.get("duration_s"),
                   "synth_s": m.get("synth_s"), "rtf": m.get("rtf")}
            try:
                hyp = engine.transcribe(str(wav), m["lang"], m["text"])
                row["hypothesis"] = hyp
                row.update({"error": error_rate(m["text"], hyp, m["lang"])})
                row["audio"] = analyze_audio(wav, m["text"], m["lang"])
                if naturalness:
                    row["naturalness"] = asr_mod.predict_naturalness(str(wav))
                counts["scored"] += 1
            except Exception as exc:  # noqa: BLE001
                row["scoring_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                counts["failed"] += 1
            sf.write(json.dumps(row, ensure_ascii=False) + "\n")
            sf.flush()
            done.add(key)
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", action="append", help="limit to these models (default: every model in OUT)")
    ap.add_argument("--asr", default="auto", help="auto | faster-whisper:large-v3 | whisper:large-v3 | mms | fake:<noise>")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--naturalness", action="store_true", help="also run the optional UTMOS predictor if it can be loaded")
    args = ap.parse_args(argv)
    out = Path(args.out)
    models = args.model or sorted(p.parent.name for p in out.glob("*/manifest.jsonl"))
    engine = asr_mod.get(args.asr, args.device)
    total = {}
    for model in models:
        total[model] = score_model(out, model, engine, args.naturalness)
        print(model, total[model])
    return 0


if __name__ == "__main__":
    sys.exit(main())
