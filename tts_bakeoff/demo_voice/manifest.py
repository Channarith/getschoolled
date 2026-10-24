"""Inventory of what the demos say, as tts_manifest/demo_voice_manifest.json.

  python3 -m tts_bakeoff.demo_voice.manifest [--langs en,es,...] [--api https://salareen.com] [--extra-texts misses.jsonl]

Sources: the On the Go demo course (public curriculum API, one course, every language it is translated into), Vision Play
(literal prompts in its JS, plus the quiz bank questions) and any extra texts (a JSON-lines file of {demo, lang, text},
for example the clips a demo reported missing) and the translated lines in tts_manifest/translations/ (demo_voice.translations; each
clip then carries the review status of its translation). Strings built at run time (scores, names, letters) are not enumerable here;
the player falls back to the default voice for them and logs the miss. The full-course demo builds its slides per learner
through the orchestrator, so it comes in through --extra-texts until a capture pass covers it.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

from .clip_hash import clip_hash, normalize, primary_lang

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tts_manifest" / "demo_voice_manifest.json"
VOICES = ROOT / "tts_manifest" / "voices.json"
DEFAULT_LANGS = ("en", "es", "zh", "vi", "th", "km", "sw", "hi")
DEMO_COURSE_ID = "audio-intro-to-machine-learning"   # apps/web/app/lib/onTheGoMode.ts
VISION_STATIC = ROOT / "subrepos" / "theodore_children_webcam_lab" / "src" / "theodore_children_webcam_lab" / "static"


def _get_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def on_the_go_lines(course: dict, lang: str) -> list[str]:
    """The exact line OnTheGo.tsx speaks per segment: "<heading>. <text>" after the audibleCourse() filter."""
    segs = [s for s in course.get("segments", []) if re.search(r"[^\W\d_]", s.get("text") or "")]
    if not segs:
        segs = course.get("segments", [])
    return [f"{s.get('heading', '')}. {s.get('text', '')}" for s in segs]


def on_the_go(langs, api: str, log=print):
    out = []
    for lang in langs:
        try:
            course = _get_json(f"{api}/curriculum/audio/courses/{DEMO_COURSE_ID}?locale={lang}")
        except Exception as exc:  # noqa: BLE001
            log(f"on_the_go {lang}: skipped ({exc})")
            continue
        if primary_lang(course.get("body_locale") or lang) != lang:
            log(f"on_the_go {lang}: not translated (body_locale={course.get('body_locale')}), skipped")
            continue
        out += [{"demo": "on_the_go", "lang": lang, "text": t} for t in on_the_go_lines(course, lang)]
    return out


_LIT = r'"((?:[^"\\\n]|\\.)*)"'
_NO_TPL = re.compile(r"\$\{")


def _lit(s: str) -> str | None:
    if "${" in s:
        return None
    try:
        return json.loads('"' + s + '"')
    except ValueError:
        return None


def vision_play(static: Path = VISION_STATIC):
    """Literal strings the Vision Play JS hands to speak(): setPrompt(title, copy[, speakText]) and speak("...")."""
    texts: list[str] = []
    for js in sorted(static.glob("*.js")):
        src = js.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'\bsetPrompt\(\s*' + _LIT + r'\s*,\s*' + _LIT + r'(?:\s*,\s*' + _LIT + r')?\s*\)', src):
            title, copy, say = (_lit(g) if g is not None else None for g in m.groups())
            if say:
                texts.append(say)
            elif title and copy:
                texts.append(f"{title}. {copy}")
        for m in re.finditer(r'\bspeak\(\s*' + _LIT + r'\s*[,)]', src):
            t = _lit(m.group(1))
            if t:
                texts.append(t)
    bank = static / "quiz_bank.json"
    if bank.is_file():
        for rows in json.loads(bank.read_text(encoding="utf-8")).values():
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict) and row.get("q"):
                    texts.append(str(row["q"]))
    return [{"demo": "vision_play", "lang": "en", "text": t} for t in texts]


def extra(path: Path | None):
    if not path:
        return []
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows.append({"demo": r.get("demo", "extra"), "lang": primary_lang(r["lang"]), "text": r["text"]})
    return rows


def build(langs=DEFAULT_LANGS, api="https://salareen.com", extra_texts=None, vision=True, log=print, translated=True) -> dict:
    from .translations import clips as translated_clips   # lazy: translations imports this module for MANIFEST
    items = on_the_go(langs, api, log) + (vision_play() if vision else []) + extra(extra_texts) + (translated_clips() if translated else [])
    seen, clips = set(), []
    for it in items:
        text = normalize(it["text"])
        if not text:
            continue
        key = (it["lang"], clip_hash(it["lang"], text))
        if key in seen:
            continue
        seen.add(key)
        clip = {"id": f"{it['demo']}:{key[0]}:{key[1]}", "demo": it["demo"], "lang": key[0], "text": text, "hash": key[1]}
        if it.get("status"):
            clip["status"] = it["status"]   # translated lines: unreviewed | ok | fixed
        clips.append(clip)
    clips.sort(key=lambda c: (c["demo"], c["lang"], c["hash"]))
    voices = json.loads(VOICES.read_text(encoding="utf-8"))["voices"]
    return {"version": 1, "hash": "cyrb53-14hex of lang+US+NFC-collapsed text", "languages": sorted({c["lang"] for c in clips}),
            "voices": voices, "clips": clips}


def refresh_offline(path: Path = MANIFEST) -> dict:
    """Re-merge voices.json and tts_manifest/translations/ into the committed manifest without calling the curriculum API."""
    from .translations import clips as translated_clips
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    clips = [c for c in m["clips"] if "status" not in c]
    seen = {(c["lang"], c["hash"]) for c in clips}
    for it in translated_clips():
        text = normalize(it["text"])
        h = clip_hash(it["lang"], text)
        if text and (it["lang"], h) not in seen:
            seen.add((it["lang"], h))
            clips.append({"id": f"{it['demo']}:{it['lang']}:{h}", "demo": it["demo"], "lang": it["lang"], "text": text, "hash": h, "status": it["status"]})
    clips.sort(key=lambda c: (c["demo"], c["lang"], c["hash"]))
    m["clips"], m["languages"] = clips, sorted({c["lang"] for c in clips})
    m["voices"] = json.loads(VOICES.read_text(encoding="utf-8"))["voices"]
    return m


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--langs", default=",".join(DEFAULT_LANGS))
    ap.add_argument("--api", default="https://salareen.com")
    ap.add_argument("--extra-texts")
    ap.add_argument("--out", default=str(MANIFEST))
    ap.add_argument("--offline", action="store_true", help="no network: keep the committed clips, re-merge voices.json and the translations")
    args = ap.parse_args(argv)
    m = refresh_offline() if args.offline else build(tuple(args.langs.split(",")), args.api, Path(args.extra_texts) if args.extra_texts else None)
    Path(args.out).write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    by = {}
    for c in m["clips"]:
        by.setdefault((c["demo"], c["lang"]), 0)
        by[(c["demo"], c["lang"])] += 1
    print(f"{len(m['clips'])} clips -> {args.out}")
    for k, v in sorted(by.items()):
        print(f"  {k[0]:12s} {k[1]:3s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
