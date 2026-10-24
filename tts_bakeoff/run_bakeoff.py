"""Synthesize the fixed sentence set with one model. Resumable. Runs on the GPU machine (Spark / iBuyPower).

  python3 -m tts_bakeoff.run_bakeoff --model voxcpm2 --check
  python3 -m tts_bakeoff.run_bakeoff --model voxcpm2 --langs km,vi --limit 5 --out runs/2026-10-24
  python3 -m tts_bakeoff.run_bakeoff --model mock --langs en,km --out /tmp/bakeoff-demo

Layout:  OUT/<model>/<lang>/<sentence id>.wav   OUT/<model>/manifest.jsonl   OUT/<model>/meta.json
Rerunning the same command skips sentences already synthesized, so a crash or Ctrl-C loses nothing.
Scoring is a separate step (score_bakeoff.py) so it can run on the Mac, away from the GPU.
"""
from __future__ import annotations

import argparse
import json
import platform
import socket
import sys
import time
from pathlib import Path

from . import adapters
from .build_sentences import load


def parse_options(pairs: list[str]) -> dict:
    out = {}
    for item in pairs or []:
        key, _, value = item.partition("=")
        out[key] = value
    return out


def done_ids(manifest: Path) -> set[tuple[str, str]]:
    done = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("status") == "ok":
                    done.add((row["lang"], row["id"]))
    return done


def run(model: str, langs: list[str], limit: int | None, out: Path, options: dict, retry_failed: bool = False) -> dict:
    adapter = adapters.get(model, **options)
    root = out / model
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.jsonl"
    done = done_ids(manifest)
    counts = {"ok": 0, "skipped": 0, "failed": 0, "unsupported": 0}
    (root / "meta.json").write_text(json.dumps({
        "model": model, "options": {k: v for k, v in options.items() if "key" not in k.lower()},
        "host": socket.gethostname(), "python": platform.python_version(), "platform": platform.platform(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }, indent=2), encoding="utf-8")
    with manifest.open("a", encoding="utf-8") as mf:
        for lang in langs:
            if not adapter.supports(lang):
                counts["unsupported"] += 1
                print(f"[{model}] {lang}: not supported by this adapter, skipping")
                continue
            for item in load(lang, limit):
                key = (lang, item["id"])
                wav = root / lang / f"{item['id']}.wav"
                if key in done and wav.exists():
                    counts["skipped"] += 1
                    continue
                row = {"model": model, "lang": lang, "id": item["id"], "text": item["text"], "wav": str(wav.relative_to(out))}
                try:
                    row.update(adapter.synthesize(item["text"], lang, wav))
                    row["status"] = "ok"
                    counts["ok"] += 1
                except Exception as exc:  # noqa: BLE001 - record and carry on; one bad sentence must not stop a long run
                    row.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
                    counts["failed"] += 1
                mf.write(json.dumps(row, ensure_ascii=False) + "\n")
                mf.flush()
                print(f"[{model}] {lang} {item['id']} {row['status']}" + (f" rtf={row.get('rtf'):.2f}" if row.get("rtf") else ""))
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help=f"adapter name: {', '.join(sorted(adapters.REGISTRY))}")
    ap.add_argument("--langs", default="km,vi,th,es,en,zh,sw,hi")
    ap.add_argument("--limit", type=int, help="first N sentences per language")
    ap.add_argument("--out", default="runs/latest")
    ap.add_argument("--option", action="append", default=[], help="adapter option key=value (repeatable)")
    ap.add_argument("--check", action="store_true", help="verify the install without loading a model, then exit")
    args = ap.parse_args(argv)
    options = parse_options(args.option)
    if args.check:
        result = adapters.get(args.model, **options).check()
        print(json.dumps(result, indent=2))
        return 0 if result["ok"] else 1
    counts = run(args.model, [x for x in args.langs.split(",") if x], args.limit, Path(args.out), options)
    print(json.dumps(counts))
    return 1 if counts["failed"] and not counts["ok"] else 0


if __name__ == "__main__":
    sys.exit(main())
