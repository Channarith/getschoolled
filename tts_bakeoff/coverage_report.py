"""Write docs/edge-voices-coverage.txt: which platform and extra languages have edge-tts voices, and what a run produced.

  python3 -m tts_bakeoff.coverage_report --run runs/2026-10-25-all [--out docs/edge-voices-coverage.txt]

Plain text. Reads edge_voices.json (the snapshot), plans the clips like edge_all.py does, and compares the plan with the run's
manifests: ok, failed, and not yet rendered clips per language.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import edge_catalog as ec
from .edge_all import build_plan
from .sentence_set import SET10, SOURCE

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO / "docs" / "edge-voices-coverage.txt"
TRANSLATION = ("xAI Grok (grok-4.20-0309-non-reasoning), one call per language plus one regeneration pass for failed sentences: 72 calls, "
               "about 33.5k input and 18.5k output tokens, roughly $0.09 at the model's list price.")


def run_status(run: Path | None, plan: list[dict]) -> dict[str, dict]:
    """lang -> {planned, ok, failed, pending, errors} from the manifests of a run."""
    seen: dict[tuple, dict] = {}
    if run:
        for mf in run.glob("*/manifest.jsonl"):
            for line in mf.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    seen[(r["model"], r["lang"], r["id"])] = r
    out: dict[str, dict] = {}
    for job in plan:
        s = out.setdefault(job["lang"], {"planned": 0, "ok": 0, "failed": 0, "pending": 0, "errors": []})
        s["planned"] += 1
        row = seen.get((job["model"], job["lang"], job["id"]))
        if row is None:
            s["pending"] += 1
        elif row.get("status") == "ok":
            s["ok"] += 1
        else:
            s["failed"] += 1
            s["errors"].append(f"{job['model']} {job['id']}")
    return out


def render(doc: dict, run: Path | None) -> str:
    catalog, voices = doc["catalog"], doc["voices"]
    plan, models = build_plan(catalog, voices)
    status = run_status(run, plan)
    spoken = [e for e in catalog.values() if e["status"] == "voice"]
    platform = [e for e in spoken if e["platform"]]
    kinds = {k: sum(1 for j in plan if models[j["model"]]["kind"] == k) for k in ("default", "style", "regional")}
    tot = {k: sum(s[k] for s in status.values()) for k in ("planned", "ok", "failed", "pending")}
    lines = [
        "EDGE-TTS VOICE COVERAGE: PLATFORM LANGUAGES AND EXTRAS",
        "",
        f"Voice snapshot: tts_bakeoff/edge_voices.json, taken {doc['retrieved']} from edge_tts.list_voices(): {doc['count']} voices.",
        f"Platform languages (packages/shared languages.py): {len(ec.PLATFORM)}; with an edge voice: {len(platform)}; without: {len(ec.PLATFORM) - len(platform)}.",
        f"Extra languages with an edge voice: {len(spoken) - len(platform)} (includes Cantonese 'yue' = zh-HK).",
        "",
        "INTERNAL REFERENCE ONLY. edge-tts is an unofficial client of Microsoft's Edge Read Aloud service. The licensed way to get the same",
        "neural voices commercially is Azure AI Speech (same voice names). Nothing here is counted as shippable.",
        "",
        "HOW THE SET IS BUILT",
        f"  Default voice rule: {ec.RULE}.",
        "  Voices we already used keep their place: " + ", ".join(f"{c} {p[0].split('-', 2)[2][:-6]}/{p[1].split('-', 2)[2][:-6]}" for c, p in ec.PINNED.items()) + ".",
        f"  10 sentences per language ({', '.join(SET10)}): the 8 languages with the full 40-sentence set (en es zh vi th km sw hi) reuse their rows exactly;",
        f"  all others are machine translations (source '{SOURCE}', review_status 'unreviewed'), checked for script, numbers, loops and copied English.",
        f"  Translation: {TRANSLATION}",
        f"  Clips: default female and male voice on all 10 sentences ({kinds['default']}); the 9 character presets on the default female for S01 and Q01 ({kinds['style']});",
        f"  every other voice of the language, one sentence each, id A01 = S01 text ({kinds['regional']}). Character presets are prosody only (rate, pitch, volume).",
        f"  Total planned: {tot['planned']} clips in {len(models)} voice folders.",
        "",
    ]
    if run:
        lines += [f"RUN: {run.name}: {tot['ok']} ok, {tot['failed']} failed, {tot['pending']} not rendered yet, of {tot['planned']} planned.", ""]
    head = f"{'LANG':<5} {'NAME':<22} {'DEFAULT F':<24} {'DEFAULT M':<24} {'VOICES':>6} {'REGIONS':>7} {'CLIPS':>6} {'OK':>5} {'FAIL':>5} {'TODO':>5}"
    for title, group in (("PLATFORM LANGUAGES", platform), ("EXTRA LANGUAGES", [e for e in spoken if not e["platform"]])):
        lines += [title, head, "-" * len(head)]
        for e in group:
            s = status.get(e["code"], {"planned": 0, "ok": 0, "failed": 0, "pending": 0})
            f, m = (e["default"][g] or "-" for g in ("female", "male"))
            short = lambda v: v if v == "-" else v.split("-", 2)[2].removesuffix("Neural") + " " + "-".join(v.split("-")[:2])  # noqa: E731
            lines.append(f"{e['code']:<5} {e['name'][:22]:<22} {short(f):<24} {short(m):<24} {e['voice_count']:>6} {len(e['regions']):>7} "
                         f"{s['planned']:>6} {s['ok']:>5} {s['failed']:>5} {s['pending']:>5}")
        lines.append("")
    lines += ["REGIONAL VARIANTS (locales per language with more than one)"]
    for e in spoken:
        if len(e["regions"]) > 1:
            lines.append(f"  {e['code']:<4} {e['name']}: " + ", ".join(f"{r['locale']} ({len(r['voices'])})" for r in e["regions"]))
    lines += ["", "LANGUAGES WITH NO EDGE VOICE (listed, never faked)"]
    for e in catalog.values():
        if e["status"] == "no_voice":
            lines += [f"  {e['code']:<4} {e['reason']}.", f"       Nearest alternative: {e['alternative']}"]
    for code, why in doc.get("skipped_extras", {}).items():
        lines.append(f"  {code:<4} {ec.NAMES[code][0]}: {why}")
    failed = [(c, s) for c, s in status.items() if s["failed"]]
    lines += ["", "FAILED CLIPS"]
    if not failed:
        lines.append("  none" if run else "  (no run given)")
    for code, s in failed:
        by_voice: dict[str, list[str]] = {}
        for item in s["errors"]:
            model, sid = item.rsplit(" ", 1)
            by_voice.setdefault(model, []).append(sid)
        lines.append(f"  {code}: {s['failed']} failed")
        for model, sids in by_voice.items():
            lines.append(f"      {model}: {', '.join(sids)}")
    if failed:
        lines += ["  The service lists these voices but answered 'No audio was received' for these clips, on every retry (4 attempts with backoff,",
                  "  then two more passes of the whole set). The same voices rendered other sentences fine, so the gaps are intermittent and per voice.",
                  "  The other default voice of the language is complete. Nothing was substituted: rerun edge_all to retry them."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", help="run folder written by edge_all.py (optional: without it the clip columns show the plan only)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    doc = json.loads(ec.SNAPSHOT.read_text(encoding="utf-8"))
    text = render(doc, Path(args.run) if args.run else None)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
