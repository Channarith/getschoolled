"""python3 -m tts_bakeoff.voice_design <command>   (run the GPU ones on the Spark: scripts/gs_run.sh --gpu -- env TORCHDYNAMO_DISABLE=1 ...)

  list                                  read-only: the registry and which voices are frozen on this machine
  check "a calm, young woman"           read-only: does a free-text description pass the real-person guard?
  freeze --voices a,b|all [--tones neutral,professional|all] [--takes 3] [--force]
                                        design each voice once and freeze the best take as its reference (GPU)
  grid --out RUN_DIR [--preset small | --voices .. --tones .. --langs en,es,km|demo|all] [--limit 3] [--freeze-missing]
                                        render the bake-off the Listening Lab loads (GPU); python3 -m tts_bakeoff.lab --out RUN_DIR
To render a stock voice for the demo like Channarith:  python3 -m tts_bakeoff.demo_voice.render run --voice stock-f-young-warm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import grid as gridmod
from . import registry
from .prompt import DescriptionRejected, TONES, validate_description


def _csv(value: str | None, everything: list[str]) -> list[str]:
    if not value or value == "all":
        return list(everything)
    return [x.strip() for x in value.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "freeze", "grid"):
        p = sub.add_parser(name)
        p.add_argument("--assets", help="voice-assets dir (default $GS_VOICE_ASSETS or ~/voice-assets)")
    sub.add_parser("check").add_argument("description")
    f = sub.choices["freeze"]
    f.add_argument("--voices", default="all")
    f.add_argument("--tones", default=registry.NEUTRAL)
    f.add_argument("--takes", type=int, default=3)
    f.add_argument("--force", action="store_true")
    g = sub.choices["grid"]
    g.add_argument("--out", required=True)
    g.add_argument("--preset", choices=("small",))
    g.add_argument("--voices", default="all")
    g.add_argument("--tones", default=registry.NEUTRAL)
    g.add_argument("--langs", default="demo", help="comma list, 'demo' (en es zh yue vi th km sw hi) or 'all' (every language with sentences)")
    g.add_argument("--limit", type=int, default=3, help="sentences per language")
    g.add_argument("--takes", type=int, default=3, help="design takes when a voice must be frozen first")
    g.add_argument("--freeze-missing", action="store_true")
    args = ap.parse_args(argv)
    all_ids = [v["id"] for v in registry.voices()]
    assets = Path(args.assets) if getattr(args, "assets", None) else None

    if args.cmd == "check":
        try:
            print("ok:", validate_description(args.description))
            return 0
        except DescriptionRejected as exc:
            print("rejected:", exc)
            return 1
    if args.cmd == "list":
        for v in registry.voices():
            row = [f"{v['id']:<24} {v['label']:<8} {v['gender']:<6} cleared langs: {','.join(v.get('langs', [])) or '-'}"]
            frozen = [t for t in [registry.NEUTRAL, *v.get("tones", [])] if registry.frozen_meta(registry.variant_id(v["id"], t), assets)]
            row.append(f"frozen here: {', '.join(frozen) if frozen else 'none'}")
            print("  ".join(row))
        return 0
    if args.cmd == "freeze":
        from .design import freeze

        voices = _csv(args.voices, all_ids)
        tones = _csv(args.tones, [registry.NEUTRAL, *TONES])
        bad = 0
        for base in voices:
            for tone in tones:
                try:
                    freeze(registry.variant_id(base, tone), assets, takes=args.takes, force=args.force)
                except registry.StockError as exc:
                    bad += 1
                    print("FAILED", exc, file=sys.stderr)
        return 1 if bad else 0
    # grid
    if args.preset == "small":
        voices, tones, langs = gridmod.SMALL["voices"], gridmod.SMALL["tones"], gridmod.SMALL["langs"]
    else:
        voices = _csv(args.voices, all_ids)
        tones = _csv(args.tones, [registry.NEUTRAL, *TONES])
        if args.langs == "demo":
            langs = list(gridmod.DEMO_LANGS)
        elif args.langs == "all":
            from tts_bakeoff.voice_clone.runner import sentence_langs

            langs = sorted(sentence_langs())
        else:
            langs = _csv(args.langs, gridmod.DEMO_LANGS)
    stats = gridmod.run(Path(args.out), voices, tones, langs, args.limit, freeze_missing=args.freeze_missing, takes=args.takes, assets=assets)
    print(json.dumps(stats))
    print(f"done. Listen: python3 -m tts_bakeoff.lab --out {args.out}")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
