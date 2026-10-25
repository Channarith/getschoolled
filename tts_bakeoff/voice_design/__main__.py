"""python3 -m tts_bakeoff.voice_design <command>   (run the GPU ones on the Spark: scripts/gs_run.sh --gpu -- env TORCHDYNAMO_DISABLE=1 ...)

  list                                  read-only: the registry and which voices are frozen on this machine
  check "a calm, young woman"           read-only: does a free-text description pass the real-person guard?
  freeze --voices a,b|all [--tones neutral,professional|all] [--takes 3] [--force]
                                        design each voice once and freeze the best take as its reference (GPU)
  grid --out RUN_DIR [--preset small|cantonese-small|cantonese-full | --voices .. --tones .. --langs en,es,km|demo|all] [--limit 3]
       [--methods en-ref,yue-ref|both] [--sentences yue] [--freeze-missing]
                                        render the bake-off the Listening Lab loads (GPU); python3 -m tts_bakeoff.lab --out RUN_DIR
  review-page --run RUN_DIR --lang yue [--out FILE]   a listening sheet for a native speaker (open it from the run folder; audio links are relative)
  apply-review decisions.json [--reviewer Wei]        record her decisions: clears the voices she approved in that language
  clear --id stock-f-young-warm --lang yue --by Wei [--tones professional,cute] [--method yue-ref|en-ref] [--note ..] [--activate] [--default]
  unclear --id ... --lang yue                          take a language back out
To render a stock voice for the demo like Channarith:  python3 -m tts_bakeoff.demo_voice.render run --voice stock-f-young-warm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import grid as gridmod
from . import registry, review
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
    g.add_argument("--preset", choices=tuple(gridmod.PRESETS))
    g.add_argument("--methods", default="en-ref", help="en-ref (designed in English), yue-ref (designed on a Cantonese sentence) or both")
    g.add_argument("--sentences", choices=("yue",), help="yue: Wei's reviewed Cantonese lines + the six-tone line when the language is yue")
    g.add_argument("--voices", default="all")
    g.add_argument("--tones", default=registry.NEUTRAL)
    g.add_argument("--langs", default="demo", help="comma list, 'demo' (en es zh yue vi th km sw hi) or 'all' (every language with sentences)")
    g.add_argument("--limit", type=int, default=3, help="sentences per language")
    g.add_argument("--takes", type=int, default=3, help="design takes when a voice must be frozen first")
    g.add_argument("--freeze-missing", action="store_true")
    rp = sub.add_parser("review-page")
    rp.add_argument("--run", required=True)
    rp.add_argument("--lang", default="yue")
    rp.add_argument("--out")
    ar = sub.add_parser("apply-review")
    ar.add_argument("decisions")
    ar.add_argument("--reviewer")
    for name in ("clear", "unclear"):
        c = sub.add_parser(name)
        c.add_argument("--id", required=True)
        c.add_argument("--lang", required=True)
    cl = sub.choices["clear"]
    cl.add_argument("--by", required=True, help="the native speaker who listened")
    cl.add_argument("--tones", default="", help="comma list of tone variants she approved (neutral is implied)")
    cl.add_argument("--method", choices=tuple(registry.METHODS), default="en-ref")
    cl.add_argument("--note", default="")
    cl.add_argument("--activate", action="store_true", help="also set active=true in tts_manifest/voices.json (the picker may then list it)")
    cl.add_argument("--default", action="store_true", help="also make it THE default Salane voice (default=true in voices.json; implies --activate)")
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
            frozen_yue = [t for t in [registry.NEUTRAL, *v.get("tones", [])] if registry.frozen_meta(registry.variant_id(v["id"], t, "yue"), assets)]
            row.append(f"frozen here: {', '.join(frozen) if frozen else 'none'}")
            if frozen_yue:
                row.append(f"frozen (Cantonese design): {', '.join(frozen_yue)}")
            for lang, rec in (v.get("cleared") or {}).items():
                row.append(f"[{lang} cleared by {rec['by']} {rec['on']}, {rec['method']}, tones: {','.join(rec['tones']) or 'neutral only'}]")
            print("  ".join(row))
        return 0
    if args.cmd == "review-page":
        out = Path(args.out) if args.out else Path(args.run) / f"review-voices-{args.lang}.html"
        out.write_text(review.page(Path(args.run), args.lang), encoding="utf-8")
        print(f"wrote {out}: open it from the run folder (the audio links are relative), then press 'Download my decisions'")
        return 0
    if args.cmd == "apply-review":
        try:
            print(json.dumps(review.apply(Path(args.decisions), args.reviewer), ensure_ascii=False, indent=1))
        except registry.StockError as exc:
            print("FAILED", exc, file=sys.stderr)
            return 1
        return 0
    if args.cmd in ("clear", "unclear"):
        try:
            if args.cmd == "unclear":
                print("removed" if registry.unclear(args.id, args.lang) else "nothing to remove")
                return 0
            tones = [t for t in args.tones.split(",") if t.strip()]
            rec = registry.clear(args.id, args.lang, args.by, tones=tones, method=args.method, note=args.note)
            print(json.dumps({args.id: {args.lang: rec}}, ensure_ascii=False))
            if args.activate or args.default:
                registry.activate(args.id)
                print(f"{args.id}: active=true in tts_manifest/voices.json (re-run `python3 -m tts_bakeoff.demo_voice.manifest --offline` to refresh the demo manifest)")
            if args.default:
                registry.set_default(args.id)
                print(f"{args.id}: default=true in tts_manifest/voices.json (the Salane Voice for visitors who have not chosen another)")
        except registry.StockError as exc:
            print("FAILED", exc, file=sys.stderr)
            return 1
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
    methods = ("en-ref", "yue-ref") if args.methods == "both" else tuple(x.strip() for x in args.methods.split(",") if x.strip())
    sentences, limit = args.sentences, args.limit
    if args.preset:
        preset = gridmod.PRESETS[args.preset]
        voices, tones, langs = preset["voices"] or list(all_ids), preset["tones"], preset["langs"]
        methods, sentences, limit = tuple(preset.get("methods", methods)), preset.get("sentences", sentences), preset.get("limit", limit)
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
    try:
        stats = gridmod.run(Path(args.out), voices, tones, langs, limit, freeze_missing=args.freeze_missing, takes=args.takes, assets=assets,
                            methods=methods, sentences=sentences)
    except registry.StockError as exc:
        print("FAILED", exc, file=sys.stderr)
        return 1
    print(json.dumps(stats))
    print(f"done. Listen: python3 -m tts_bakeoff.lab --out {args.out}")
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
