#!/usr/bin/env python3
"""Fill the mobile app's missing UI strings with machine translations (xAI Grok), as the lowest-priority layer.

  python3 scripts/mobile_i18n_fill.py status
  python3 scripts/mobile_i18n_fill.py plan  [--langs th,sw]
  python3 scripts/mobile_i18n_fill.py run   [--langs th,sw] [--max-usd 6] [--workers 8]

Reads apps/mobile/src/i18n/strings.ts (English source and the hand-written dictionaries), languages.ts, gapFill.json and
uiPack.json, works out which keys each language still lacks, translates only those, and writes
apps/mobile/src/i18n/machineFill.json. strings.ts layers it UNDER every hand-written string, so it only fills gaps and never
overrides a human translation. Every entry is a machine translation and needs a native-speaker pass (machineFill.meta.json).
The key comes from XAI_API_KEY and is never printed or written. Placeholders such as {n} must survive unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "apps" / "mobile" / "src" / "i18n"
OUT = I18N / "machineFill.json"
META = I18N / "machineFill.meta.json"
MODEL = os.environ.get("XAI_TEXT_MODEL_LAB", "grok-4.20-0309-non-reasoning")
USD_PER_M_IN, USD_PER_M_OUT = 1.25, 2.50
BATCH = 30
EST_IN, EST_OUT = 1700, 3200
PLACEHOLDER = re.compile(r"\{[A-Za-z0-9_]+\}")
LINE = re.compile(r'^\s*"([^"\\]+)":\s*("(?:[^"\\]|\\.)*"),?\s*$')
# English varieties are handled by englishVariety.ts, never translated here.
SKIP = {"en", "en-GB", "en-AU", "en-SG"}
NAMES = {
    "es": "Spanish (Latin American)", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese (Brazil)",
    "ru": "Russian", "ar": "Arabic (Modern Standard)", "hi": "Hindi", "zh": "Mandarin Chinese (Simplified)",
    "yue": "Cantonese (Hong Kong), written colloquial Cantonese in Traditional Chinese characters, NOT Mandarin",
    "ja": "Japanese", "ko": "Korean", "vi": "Vietnamese", "th": "Thai", "km": "Khmer", "sw": "Swahili", "id": "Indonesian",
    "nl": "Dutch", "pl": "Polish", "uk": "Ukrainian", "tr": "Turkish", "he": "Hebrew", "bn": "Bengali", "ur": "Urdu",
    "fa": "Persian (Farsi)", "el": "Greek", "cs": "Czech",
}
SYSTEM = (
    "You translate user-interface strings for a learning app (phone app: buttons, labels, short sentences). Rules: be faithful; "
    "natural wording a native app would use; keep placeholders like {n} {name} {days} exactly as written; keep brand names "
    "(Salareen, Salane, Sala, xAI, Grok) and emoji as they are; keep letter case style (ALL CAPS section titles stay capitalised "
    "where the script has case); keep it short, similar length to English; no notes, no quotes, no markup. Return ONLY a JSON "
    "object mapping each given key to its translation."
)


def english() -> dict[str, str]:
    text = (I18N / "strings.ts").read_text(encoding="utf-8")
    start = text.index("const EN: Record<StringKey, string> = {")
    out: dict[str, str] = {}
    for line in text[start:].splitlines()[1:]:
        if line.startswith("};"):
            break
        m = LINE.match(line)
        if m:
            out[m.group(1)] = json.loads(m.group(2))
    return out


def codes() -> list[str]:
    text = (I18N / "languages.ts").read_text(encoding="utf-8")
    return re.findall(r'code:\s*"([A-Za-z-]+)"', text)


def have_keys(lang: str) -> set[str]:
    """Keys a language already has from hand-written blocks and the other JSON packs (not machineFill itself)."""
    text = (I18N / "strings.ts").read_text(encoding="utf-8")
    keys: set[str] = set()
    m = re.search(r"const %s: [^=]*= \{" % re.escape(lang.upper()), text)
    if m:
        for line in text[m.end():].splitlines():
            if line.startswith("};"):
                break
            mm = LINE.match(line)
            if mm:
                keys.add(mm.group(1))
    for name in ("gapFill.json", "uiPack.json"):
        pack = json.loads((I18N / name).read_text(encoding="utf-8"))
        keys |= set(pack.get(lang, {}))
    return keys


def load_out() -> dict[str, dict[str, str]]:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}


def pending(lang: str, en: dict[str, str], done: dict[str, dict[str, str]]) -> list[str]:
    have = have_keys(lang) | set(done.get(lang, {}))
    return [k for k, v in en.items() if k not in have and re.search(r"[A-Za-z]", PLACEHOLDER.sub("", v))]


def estimate(n: int) -> float:
    return math.ceil(n / BATCH) * (EST_IN * USD_PER_M_IN + EST_OUT * USD_PER_M_OUT) / 1e6


def bad(en: str, text) -> bool:
    if not isinstance(text, str) or not text.strip() or re.search(r"[<>]|```", text):
        return True
    return sorted(PLACEHOLDER.findall(en)) != sorted(PLACEHOLDER.findall(text))


def call(lang: str, batch: dict[str, str], key: str) -> tuple[dict, dict]:
    payload = {"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Translate into {NAMES.get(lang, lang)} (code {lang}). Strings:\n" + json.dumps(batch, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.x.ai/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json", "authorization": f"Bearer {key}", "user-agent": "salareen-i18n/1"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:  # noqa: S310
                body = json.loads(r.read().decode())
            return json.loads(body["choices"][0]["message"]["content"]), body.get("usage", {})
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{lang}: {type(last).__name__}")


def translate_batch(lang: str, keys: list[str], en: dict[str, str], key: str, usage: dict, caller=call) -> dict[str, str]:
    got: dict[str, str] = {}
    todo = list(keys)
    for _ in range(2):  # one regeneration pass for lines that fail the placeholder checks
        if not todo:
            break
        reply, u = caller(lang, {k: en[k] for k in todo}, key)
        usage["in"] += u.get("prompt_tokens", 0)
        usage["out"] += u.get("completion_tokens", 0)
        for k in todo:
            if not bad(en[k], reply.get(k)):
                got[k] = reply[k].strip()
        todo = [k for k in todo if k not in got]
    return got


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("status", "plan", "run"))
    ap.add_argument("--langs", default="")
    ap.add_argument("--max-usd", type=float, default=6.0)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    en = english()
    done = load_out()
    langs = [l for l in (a.langs.split(",") if a.langs else codes()) if l and l not in SKIP]
    rows = {l: pending(l, en, done) for l in langs}
    total = sum(len(v) for v in rows.values())
    cost = estimate(total)
    if a.cmd in ("status", "plan"):
        for l, keys in rows.items():
            print(f"{l:4} missing {len(keys):4} of {len(en)}  (machine-filled so far: {len(done.get(l, {}))})")
        print(f"total {total} strings; estimated ${cost:.2f} (worst case ${2 * cost:.2f})")
        return 0
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        print("XAI_API_KEY is not set", file=sys.stderr)
        return 2
    if cost > a.max_usd:
        print(f"estimated ${cost:.2f} is over --max-usd {a.max_usd:.2f}", file=sys.stderr)
        return 2
    usage = {"in": 0, "out": 0}
    jobs = [(l, keys[i:i + BATCH]) for l, keys in rows.items() for i in range(0, len(keys), BATCH)]
    failed = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(translate_batch, l, ks, en, key, usage): (l, ks) for l, ks in jobs}
        for n, fut in enumerate(as_completed(futs), 1):
            l, ks = futs[fut]
            try:
                got = fut.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[{n}/{len(jobs)}] {l}: {type(exc).__name__}", flush=True)
                failed += len(ks)
                continue
            done.setdefault(l, {}).update(got)
            failed += len(ks) - len(got)
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            spent = (usage["in"] * USD_PER_M_IN + usage["out"] * USD_PER_M_OUT) / 1e6
            print(f"[{n}/{len(jobs)}] {l} +{len(got)}/{len(ks)}  spent ${spent:.2f}", flush=True)
            if spent > a.max_usd:
                print("spend cap reached; stopping", flush=True)
                break
    META.write_text(json.dumps({"source": "grok-translation", "model": MODEL, "status": "unreviewed (machine translation, needs a native-speaker pass)",
                                "languages": sorted(done), "strings": {l: len(v) for l, v in sorted(done.items())}}, indent=1) + "\n", encoding="utf-8")
    print(f"done; {failed} strings still missing (rerun to retry); tokens in={usage['in']} out={usage['out']}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
