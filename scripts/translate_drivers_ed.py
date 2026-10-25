#!/usr/bin/env python3
"""Translate the driver's ed demo into the languages that still speak English.

The demo only had a hand-written Khmer overlay. Every other language kept the
English words, so the voice stayed English. This writes one JSON file per
language under data/cert_machine (or AOEP_CERT_MACHINE_DIR). Course Studio
reads a slide as soon as its title, body, and spoken line are in that file.

  python3 scripts/translate_drivers_ed.py --plan
  python3 scripts/translate_drivers_ed.py --share mac      # es, fr on this Mac
  python3 scripts/translate_drivers_ed.py --share spark    # the long GPU share
  python3 scripts/translate_drivers_ed.py --share kalel    # the 8 GB share
  python3 scripts/translate_drivers_ed.py --languages es,fr

Khmer is skipped: it is already curated. Finished strings are skipped, so stop
and rerun any time. Run it under scripts/gs_run.sh (see translate_drivers_ed.sh).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
sys.path.insert(0, str(ROOT / "subrepos" / "theodore_course_studio" / "src"))

SHARES = {
    # Spanish and French stay on the Mac: those are the languages the demo was
    # asked for, and this is the machine that plays them. The Spark GPU takes
    # the long share. No language is on two machines.
    "mac": ("es", "fr"),
    "spark": (
        "de", "it", "pt", "nl", "pl", "ru", "uk", "tr", "ar", "he", "hi",
        "bn", "ur", "fa", "zh", "ja", "ko", "vi",
    ),
    "kalel": ("th", "id", "sw", "el", "cs"),
}
TEXT_FIELDS = ("title", "body", "say", "activity", "quiz_prompt", "quiz_explanation", "game_prompt")
LIST_FIELDS = ("examples", "quiz_choices", "game_options", "game_steps")
_LETTERS = re.compile(r"[A-Za-z]{4,}")


def output_dir() -> Path:
    override = os.environ.get("AOEP_CERT_MACHINE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return ROOT / "data" / "cert_machine"


def _build_english() -> tuple[list[dict], dict[str, str]]:
    """Pull the spoken English out of the driver's ed lessons. Order is course order,
    so the 10-minute demo (the opening lesson) is translated before the later lessons."""
    from theodore_course_studio.cert_i18n import SCAFFOLD_EN
    from theodore_course_studio.cert_multimodal import kit_for_slide
    from theodore_course_studio.certification_prep import CertTrackId, _TEMPLATES
    from theodore_course_studio.slide_keys import slide_key_for

    rows = []
    for template in _TEMPLATES:
        if template.track is not CertTrackId.CA_DMV_PERMIT:
            continue
        for beat in template.beats:
            key = beat.key or slide_key_for(beat.title, lesson_id=template.lesson_id)
            kit = kit_for_slide(slide_key=key, title=beat.title, body=beat.body)
            rows.append({
                "key": key,
                "lesson_id": template.lesson_id,
                "title": beat.title,
                "body": beat.body,
                "say": beat.say,
                "activity": beat.activity,
                "examples": list(kit.examples),
                "quiz_prompt": kit.quiz_prompt,
                "quiz_choices": list(kit.quiz_choices),
                "quiz_explanation": kit.quiz_explanation,
                "game_prompt": kit.game_prompt,
                "game_options": list(kit.game_options),
                "game_steps": list(kit.game_steps),
            })
    scaffold = {
        "examples_heading": SCAFFOLD_EN.examples_heading,
        "examples_lead": SCAFFOLD_EN.examples_lead,
    }
    return rows, scaffold


def load_english() -> tuple[list[dict], dict[str, str]]:
    """English source. A snapshot at data/cert_machine/_english.json lets the
    Spark and the iBuyPower box translate without this Mac's checkout."""
    path = output_dir() / "_english.json"
    if path.is_file():
        doc = json.loads(path.read_text(encoding="utf-8"))
        slides = doc.get("slides")
        scaffold = doc.get("scaffold") if isinstance(doc.get("scaffold"), dict) else {}
        if isinstance(slides, list) and slides:
            return slides, scaffold
    slides, scaffold = _build_english()
    path.parent.mkdir(parents=True, exist_ok=True)
    _save(path, {"scaffold": scaffold, "slides": slides})
    print(f"wrote {path}", flush=True)
    return slides, scaffold


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def accepted(english: str, translated: str) -> bool:
    got = _clean(translated)
    src = _clean(english)
    if not got:
        return False
    if got.casefold() == src.casefold() and _LETTERS.search(src):
        return False
    return True


def _pending_strings(english: dict, have: dict) -> list[tuple[str, str]]:
    """(field path, english) still missing or rejected."""
    out = []
    for name in TEXT_FIELDS:
        src = _clean(english.get(name) or "")
        if not src:
            continue
        got = _clean((have or {}).get(name) or "")
        if not accepted(src, got):
            out.append((name, src))
    for name in LIST_FIELDS:
        src_list = [_clean(x) for x in english.get(name) or [] if _clean(x)]
        got_list = list((have or {}).get(name) or [])
        for i, src in enumerate(src_list):
            got = _clean(got_list[i]) if i < len(got_list) else ""
            if not accepted(src, got):
                out.append((f"{name}.{i}", src))
    return out


def _store(slide: dict, path: str, text: str) -> None:
    if "." not in path:
        slide[path] = text
        return
    name, index = path.split(".", 1)
    slot = slide.setdefault(name, [])
    i = int(index)
    while len(slot) <= i:
        slot.append("")
    slot[i] = text


def _load(path: Path) -> dict:
    if not path.is_file():
        return {"scaffold": {}, "slides": {}}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"scaffold": {}, "slides": {}}
    doc.setdefault("scaffold", {})
    doc.setdefault("slides", {})
    return doc


def _save(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def _translate_many(pairs: list[tuple[str, str]], lang: str) -> list[str]:
    from aoep_shared.nllb import translate_batch

    batch = int(os.environ.get("NLLB_BATCH_SIZE") or "8")
    return translate_batch([text for _path, text in pairs], source="en", target=lang, batch_size=batch)


def translate_language(lang: str, slides: list[dict], scaffold_en: dict, dest: Path) -> tuple[int, int]:
    path = dest / f"{lang}.json"
    doc = _load(path)
    doc["language"] = lang
    doc["engine"] = "nllb"
    doc["track"] = "ca_dmv_permit"
    pending: list[tuple[str, str, str]] = []  # slide key or "scaffold", field, english
    scaffold = doc.setdefault("scaffold", {})
    for field in ("examples_heading", "examples_lead"):
        src = _clean(scaffold_en.get(field) or "")
        if not src:
            continue
        if not accepted(src, scaffold.get(field) or ""):
            pending.append(("scaffold", field, src))
    stored = doc.setdefault("slides", {})
    for slide in slides:
        have = stored.get(slide["key"]) if isinstance(stored.get(slide["key"]), dict) else {}
        for field, src in _pending_strings(slide, have):
            pending.append((slide["key"], field, src))
    total = len(pending)
    if not total:
        print(f"{lang}: already complete ({len(slides)} slides)", flush=True)
        return 0, 0
    print(f"{lang}: {total} strings to translate", flush=True)
    done = 0
    step = max(1, int(os.environ.get("NLLB_BATCH_SIZE") or "8"))
    for start in range(0, total, step):
        chunk = pending[start:start + step]
        try:
            translated = _translate_many([(field, src) for _key, field, src in chunk], lang)
        except Exception as exc:  # noqa: BLE001 — leave the file as it was and stop this language
            print(f"{lang}: stopped after {done}/{total}: {exc}", flush=True)
            return done, total
        if len(translated) != len(chunk):
            print(f"{lang}: batch returned {len(translated)} lines for {len(chunk)}", flush=True)
            return done, total
        for (key, field, src), got in zip(chunk, translated):
            if not accepted(src, got):
                continue
            if key == "scaffold":
                doc["scaffold"][field] = _clean(got)
            else:
                row = stored.setdefault(key, {})
                _store(row, field, _clean(got))
            done += 1
        _save(path, doc)
        print(f"{lang}: {done}/{total}", flush=True)
    return done, total


def string_count(slides: list[dict], scaffold_en: dict) -> int:
    n = sum(1 for field in ("examples_heading", "examples_lead") if _clean(scaffold_en.get(field) or ""))
    for slide in slides:
        n += len(_pending_strings(slide, {}))
    return n


def _ready(slide: dict, have: dict) -> bool:
    for field in ("title", "body", "say"):
        src = _clean(slide.get(field) or "")
        if not src or not accepted(src, (have or {}).get(field) or ""):
            return False
    return True


def print_status() -> int:
    slides, scaffold_en = load_english()
    dest = output_dir()
    total = string_count(slides, scaffold_en)
    opening = [s for s in slides if s.get("lesson_id") == "ca-dmv-basics"]
    print(f"slides {len(slides)}  strings/language {total}  dir {dest}", flush=True)
    print(f"10-minute demo starts on ca-dmv-basics ({len(opening)} slides)", flush=True)
    for share, langs in SHARES.items():
        print(f"[{share}]", flush=True)
        for lang in langs:
            path = dest / f"{lang}.json"
            doc = _load(path) if path.is_file() else {"slides": {}, "scaffold": {}}
            stored = doc.get("slides") if isinstance(doc.get("slides"), dict) else {}
            left = 0
            scaffold = doc.get("scaffold") if isinstance(doc.get("scaffold"), dict) else {}
            for field in ("examples_heading", "examples_lead"):
                src = _clean(scaffold_en.get(field) or "")
                if src and not accepted(src, scaffold.get(field) or ""):
                    left += 1
            ready = 0
            opening_ready = 0
            for slide in slides:
                have = stored.get(slide["key"]) if isinstance(stored.get(slide["key"]), dict) else {}
                left += len(_pending_strings(slide, have))
                if _ready(slide, have):
                    ready += 1
                    if slide.get("lesson_id") == "ca-dmv-basics":
                        opening_ready += 1
            print(
                f"  {lang}: {ready}/{len(slides)} slides speak  "
                f"basics {opening_ready}/{len(opening)}  strings left {left}/{total}",
                flush=True,
            )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--share", choices=sorted(SHARES), help="which machine's language list")
    ap.add_argument("--languages", default="", help="comma list; overrides --share")
    ap.add_argument("--plan", action="store_true", help="print the work and translate nothing")
    ap.add_argument("--status", action="store_true", help="show how many slides already speak each language")
    args = ap.parse_args()
    if args.status:
        return print_status()
    if args.languages:
        langs = tuple(x.strip() for x in args.languages.split(",") if x.strip())
        grouped = (("custom", langs),)
    elif args.share:
        langs = SHARES[args.share]
        grouped = ((args.share, langs),)
    elif args.plan:
        langs = tuple(lang for group in SHARES.values() for lang in group)
        grouped = tuple(SHARES.items())
    else:
        ap.error("pass --share, --languages, --plan, or --status")
    slides, scaffold_en = load_english()
    each = string_count(slides, scaffold_en)
    print(f"driver's ed slides: {len(slides)}  strings per language: {each}", flush=True)
    if args.plan:
        for share, group in grouped:
            print(f"  {share}: {' '.join(group)}", flush=True)
        return 0
    dest = output_dir()
    print(f"writing {dest}", flush=True)
    for lang in langs:
        if lang == "en":
            continue
        translate_language(lang, slides, scaffold_en, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
