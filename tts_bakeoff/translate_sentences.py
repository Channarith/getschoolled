"""Translate the 10 listening sentences into every platform and extra language with the xAI Grok API.

  python3 -m tts_bakeoff.translate_sentences --dry-run          # call count and cost estimate, nothing sent
  python3 -m tts_bakeoff.translate_sentences [--langs ar,he] [--max-usd 1.0] [--force]

One API call per language (the 10 English sentences in, a JSON object out). The estimate is printed first and the run refuses
to start above --max-usd. Output is checked with sentence_set.problems (script, numbers, loops, markup, unchanged-from-English);
sentences that fail are regenerated once. Files that already exist are skipped unless --force. The key comes from XAI_API_KEY
and is never printed or written. Rows are 'unreviewed' machine translations (source grok-translation-v1).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from .build_sentences import CATEGORIES
from .edge_catalog import NAMES, PLATFORM, extra_codes, load_voices
from .sentence_set import FULL_SET_LANGS, SET10, SOURCE, path_for, problems
from .sentences_master import SENTENCES

MODEL = os.environ.get("XAI_TEXT_MODEL_LAB", "grok-4.20-0309-non-reasoning")
USD_PER_M_IN, USD_PER_M_OUT = 1.25, 2.50  # list price of the model above (xAI /v1/language-models, 2026-10-24)
EST_TOKENS_IN, EST_TOKENS_OUT = 650, 1400  # per call; scripts like Burmese or Amharic tokenize long, so this is generous

SYSTEM = (
    "You translate short spoken lesson sentences for a text-to-speech listening test. Rules: be faithful to the English; use "
    "natural, spoken-style wording a teacher would say aloud; keep numbers and proper names (write numbers as the English does: "
    "as words if the source spells them out); translate vocabulary words too; when the script is not Latin write personal names in that script; no notes, no quotes, no markup. Write in the language's "
    "normal script (Cantonese: written Cantonese in traditional characters; Serbian: Cyrillic). Return ONLY a JSON object that maps "
    "each given id to its translation."
)


def targets() -> list[str]:
    codes = [c for c in list(PLATFORM) + extra_codes(load_voices()) if c not in FULL_SET_LANGS]
    return list(dict.fromkeys(codes))


def estimate(n_calls: int) -> float:
    return n_calls * (EST_TOKENS_IN * USD_PER_M_IN + EST_TOKENS_OUT * USD_PER_M_OUT) / 1e6


def call(lang: str, ids: tuple[str, ...], key: str) -> tuple[dict, dict]:
    name = NAMES[lang][0]
    payload = {"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Translate into {name} (code {lang}). Sentences:\n" + json.dumps({i: SENTENCES[i]["en"] for i in ids}, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.x.ai/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json", "authorization": f"Bearer {key}", "user-agent": "tts-bakeoff/1"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
                body = json.loads(r.read().decode())
            content = body["choices"][0]["message"]["content"]
            return json.loads(content), body.get("usage", {})
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{lang}: {type(last).__name__}")


def row(lang: str, sid: str, text: str) -> dict:
    return {"id": sid, "lang": lang, "category": CATEGORIES[sid[0]], "text": text.strip(), "ref_en": SENTENCES[sid]["en"],
            "source": SOURCE, "review_status": "unreviewed"}


def translate_language(lang: str, key: str, usage: dict) -> tuple[list[dict], list[str]]:
    got: dict[str, str] = {}
    left = SET10
    for attempt in range(2):  # first try, then one regeneration of the failures
        data, u = call(lang, left, key)
        usage["in"] += u.get("prompt_tokens", 0)
        usage["out"] += u.get("completion_tokens", 0)
        usage["calls"] += 1
        for sid in left:
            text = data.get(sid)
            if isinstance(text, str) and not problems(lang, row(lang, sid, text), SENTENCES[sid]["en"]):
                got[sid] = text
        left = tuple(i for i in SET10 if i not in got)
        if not left:
            break
    return [row(lang, i, got[i]) for i in SET10 if i in got], [f"{lang} {i}" for i in left]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--langs")
    ap.add_argument("--max-usd", type=float, default=1.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    langs = args.langs.split(",") if args.langs else targets()
    todo = [lang for lang in langs if args.force or not path_for(lang).exists()]
    cost = estimate(len(todo))
    print(f"{len(todo)} languages to translate ({len(langs) - len(todo)} already done), about {len(todo)} calls ({len(todo) * 2} worst case with regeneration), "
          f"model {MODEL}, estimated cost ${cost:.2f} (worst case ${2 * cost:.2f}), cap ${args.max_usd:.2f}", flush=True)
    if args.dry_run or not todo:
        return 0
    if cost > args.max_usd:
        print("estimate is above the cap: stopping", file=sys.stderr)
        return 2
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        print("XAI_API_KEY is not set: stopping (NLLB is the documented fallback, and only when its dependencies import)", file=sys.stderr)
        return 2
    usage = {"in": 0, "out": 0, "calls": 0}
    failed: list[str] = []
    for lang in todo:
        rows, bad = translate_language(lang, key, usage)
        failed += bad
        if len(rows) == len(SET10):
            path_for(lang).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
        spent = (usage["in"] * USD_PER_M_IN + usage["out"] * USD_PER_M_OUT) / 1e6
        print(f"{lang}: {len(rows)}/{len(SET10)} ok{' FAILED ' + ','.join(bad) if bad else ''} | calls {usage['calls']} spent ${spent:.3f}", flush=True)
        if spent > args.max_usd:
            print("spend cap reached: stopping", file=sys.stderr)
            return 2
    print(json.dumps({"calls": usage["calls"], "tokens_in": usage["in"], "tokens_out": usage["out"],
                      "usd": round((usage["in"] * USD_PER_M_IN + usage["out"] * USD_PER_M_OUT) / 1e6, 4), "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
