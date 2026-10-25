"""Translations of the demo lines for languages the curriculum API does not cover (Cantonese first), with native-speaker review.

  python3 -m tts_bakeoff.demo_voice.translations plan   [--langs yue]            # line count and cost estimate, nothing sent
  python3 -m tts_bakeoff.demo_voice.translations run    [--langs yue] [--max-usd 1.0]
  python3 -m tts_bakeoff.demo_voice.translations status
  python3 -m tts_bakeoff.demo_voice.translations review-page --lang yue --out review-yue.html
  python3 -m tts_bakeoff.demo_voice.translations apply-review decisions.json [--reviewer "Wei Miao"]

Source lines are the English clips of tts_manifest/demo_voice_manifest.json (the On the Go course plus Vision Play). One xAI Grok
call per batch of lines; the key comes from XAI_API_KEY and is never printed or written. Output goes to
tts_manifest/translations/<lang>.json as machine translations with status 'unreviewed'. The review page is one self-contained HTML
file (no network): a native speaker marks each line OK, or edits the text, or flags it, and downloads a decisions file that
apply-review merges back. Status: unreviewed (machine), ok (reviewer accepted), fixed (reviewer corrected), needs_fix (flagged, left out
of the manifest until fixed). The manifest picks up every line except needs_fix.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .clip_hash import clip_hash, normalize
from .manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[2]
TRANS_DIR = ROOT / "tts_manifest" / "translations"
SOURCE = "grok-translation-v1"
MODEL = os.environ.get("XAI_TEXT_MODEL_LAB", "grok-4.20-0309-non-reasoning")
USD_PER_M_IN, USD_PER_M_OUT = 1.25, 2.50   # same list price tts_bakeoff.translate_sentences uses
BATCH = 25
EST_IN, EST_OUT = 1400, 2600                # tokens per batch of BATCH lines; generous for CJK and Khmer/Thai
STATUSES = ("unreviewed", "ok", "fixed", "needs_fix")
IN_MANIFEST = ("unreviewed", "ok", "fixed")
DEFAULT_LANGS = ("yue",)
OTHER_DEMO_LANGS = ("zh", "es", "vi", "th", "km", "sw", "hi")   # Vision Play is English-only today; opt in with --langs

LANG_NAMES = {
    "yue": "Cantonese (Hong Kong): written colloquial Cantonese in Traditional Chinese characters, spoken register, NOT Mandarin; "
           "use particles like 嘅 咗 喺 唔 咩 啦 㗎 where a Hong Kong teacher would say them",
    "zh": "Mandarin Chinese (Simplified characters)", "es": "Spanish (Latin American)", "vi": "Vietnamese", "th": "Thai",
    "km": "Khmer", "sw": "Swahili", "hi": "Hindi",
}
SYSTEM = (
    "You translate short spoken lines for a children's and adult learning app, to be read aloud by a text-to-speech voice. Rules: "
    "be faithful to the English; natural spoken wording a teacher would say aloud; keep numbers, emoji-free; keep brand names "
    "(Salareen, Salane) and code or file names as they are; keep punctuation that marks pauses; no notes, no quotes, no markup, "
    "no explanations. Return ONLY a JSON object mapping each given id to its translation."
)
_CJK = re.compile(r"[㐀-鿿]")
_MARKUP = re.compile(r"[<>{}]|```")


def path_for(lang: str) -> Path:
    return TRANS_DIR / f"{lang}.json"


def load(lang: str) -> dict:
    p = path_for(lang)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"lang": lang, "source": SOURCE, "model": MODEL, "items": {}}


def save(doc: dict) -> None:
    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    path_for(doc["lang"]).write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def english_sources(manifest_path: Path = MANIFEST) -> list[dict]:
    """Unique English demo lines: [{src, demo, en}], src = the English clip hash (stable id across languages)."""
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    seen, out = set(), []
    for c in m["clips"]:
        if c["lang"] == "en" and c["hash"] not in seen:
            seen.add(c["hash"])
            out.append({"src": c["hash"], "demo": c["demo"], "en": c["text"]})
    return out


def pending(lang: str, sources: list[dict]) -> list[dict]:
    have = load(lang)["items"]
    return [s for s in sources if s["src"] not in have]


def estimate(n_lines: int) -> float:
    return math.ceil(n_lines / BATCH) * (EST_IN * USD_PER_M_IN + EST_OUT * USD_PER_M_OUT) / 1e6


def problems(lang: str, en: str, text) -> list[str]:
    if not isinstance(text, str) or not normalize(text):
        return ["empty"]
    out = []
    if _MARKUP.search(text):
        out.append("markup")
    if lang in ("yue", "zh") and not _CJK.search(text):
        out.append("not Chinese script")
    if normalize(text) == normalize(en) and re.search(r"[A-Za-z]{4,}", en):
        out.append("unchanged from English")
    en_nums, tx_nums = re.findall(r"\d+", en), re.findall(r"\d+", text)
    if lang not in ("yue", "zh") and en_nums and not all(n in tx_nums for n in en_nums):   # Chinese writes 144 as 一百四十四: fine to speak
        out.append("numbers differ")
    if len(text) > 4 * max(len(en), 20) + 40:
        out.append("far too long")
    return out


def call(lang: str, batch: list[dict], key: str) -> tuple[dict, dict]:
    name = LANG_NAMES.get(lang, lang)
    payload = {"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Translate into {name} (code {lang}). Lines:\n" + json.dumps({s["src"]: s["en"] for s in batch}, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.x.ai/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"content-type": "application/json", "authorization": f"Bearer {key}", "user-agent": "tts-bakeoff/1"})
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


def translate_language(lang: str, todo: list[dict], key: str, usage: dict, caller=call) -> list[str]:
    """Translate every pending line in batches, one regeneration pass for lines that fail the checks. Returns failed ids."""
    doc = load(lang)
    left = list(todo)
    for _ in range(2):
        retry = []
        for i in range(0, len(left), BATCH):
            batch = left[i:i + BATCH]
            data, u = caller(lang, batch, key)
            usage["in"] += u.get("prompt_tokens", 0)
            usage["out"] += u.get("completion_tokens", 0)
            usage["calls"] += 1
            for s in batch:
                text = data.get(s["src"])
                if problems(lang, s["en"], text):
                    retry.append(s)
                else:
                    doc["items"][s["src"]] = {"demo": s["demo"], "en": s["en"], "text": normalize(text), "status": "unreviewed"}
        left = retry
        save(doc)
        if not left:
            break
    return [s["src"] for s in left]


def review_page(lang: str) -> str:
    doc = load(lang)
    rows = [{"src": k, "demo": v["demo"], "en": v["en"], "text": v["text"], "status": v["status"]} for k, v in sorted(doc["items"].items(), key=lambda kv: (kv[1]["demo"], kv[1]["en"]))]
    data = json.dumps({"lang": lang, "rows": rows}, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"Review: demo lines in {lang}")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font:16px/1.5 system-ui,"PingFang HK","Noto Sans CJK TC",sans-serif;margin:0;background:#f6f4ef;color:#222}}
header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
main{{max-width:980px;margin:0 auto;padding:12px 16px 80px}}
.row{{background:#fff;border:1px solid #e3ded3;border-radius:8px;padding:10px 12px;margin:10px 0}}
.row.ok{{border-left:6px solid #2e7d32}} .row.needs_fix{{border-left:6px solid #c62828}} .row.fixed{{border-left:6px solid #1565c0}}
.en{{color:#555;font-size:14px}} .demo{{font-size:12px;color:#888}}
textarea{{width:100%;box-sizing:border-box;font:inherit;min-height:3em;margin:6px 0}}
button,label{{font:inherit}} button{{padding:6px 12px;border-radius:6px;border:1px solid #888;background:#fff;cursor:pointer}}
button.primary{{background:#7a5320;color:#fff;border-color:#7a5320}}
.bar{{height:8px;background:#e7e2d7;border-radius:4px;overflow:hidden;width:200px}} .bar i{{display:block;height:100%;background:#2e7d32}}
</style></head><body>
<header><strong>Check each line: does it sound natural when read aloud?</strong>
<span id="count"></span><span class="bar"><i id="fill"></i></span>
<label>Your name <input id="who" size="16" placeholder="reviewer"></label>
<button class="primary" id="dl">Download my decisions</button>
<label><input type="checkbox" id="todo"> only unchecked</label></header>
<main id="list"></main>
<script>
const DATA = {data};
const KEY = "review-" + DATA.lang;
const saved = JSON.parse(localStorage.getItem(KEY) || "{{}}");
const state = {{}};
for (const r of DATA.rows) state[r.src] = saved[r.src] || {{status: r.status, text: r.text}};
const list = document.getElementById("list");
function paint() {{
  const only = document.getElementById("todo").checked;
  list.innerHTML = "";
  for (const r of DATA.rows) {{
    const s = state[r.src];
    if (only && (s.status === "ok" || s.status === "fixed")) continue;
    const d = document.createElement("div"); d.className = "row " + s.status;
    d.innerHTML = '<div class="demo"></div><div class="en"></div><textarea></textarea><div><button data-a="ok">OK</button> <button data-a="needs_fix">Needs a fix</button></div>';
    d.querySelector(".demo").textContent = r.demo; d.querySelector(".en").textContent = r.en;
    const ta = d.querySelector("textarea"); ta.value = s.text; ta.lang = DATA.lang === "yue" ? "yue-Hant-HK" : DATA.lang;
    ta.oninput = () => {{ s.text = ta.value; s.status = ta.value.trim() === r.text ? (s.status === "fixed" ? "unreviewed" : s.status) : "fixed"; save(); count(); d.className = "row " + s.status; }};
    d.querySelectorAll("button").forEach(b => b.onclick = () => {{ s.status = b.dataset.a === "ok" ? (ta.value.trim() === r.text ? "ok" : "fixed") : "needs_fix"; save(); paint(); }});
    list.appendChild(d);
  }}
  count();
}}
function save() {{ localStorage.setItem(KEY, JSON.stringify(state)); }}
function count() {{
  const done = DATA.rows.filter(r => ["ok", "fixed"].includes(state[r.src].status)).length;
  document.getElementById("count").textContent = done + " / " + DATA.rows.length + " checked";
  document.getElementById("fill").style.width = (100 * done / DATA.rows.length) + "%";
}}
document.getElementById("todo").onchange = paint;
document.getElementById("dl").onclick = () => {{
  const decisions = {{}};
  for (const r of DATA.rows) {{ const s = state[r.src]; if (s.status !== "unreviewed") decisions[r.src] = {{status: s.status, text: s.text.trim()}}; }}
  const blob = new Blob([JSON.stringify({{lang: DATA.lang, reviewer: document.getElementById("who").value.trim(), decisions}}, null, 1)], {{type: "application/json"}});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "review-" + DATA.lang + "-decisions.json"; a.click();
}};
paint();
</script></body></html>"""


def apply_review(decisions_path: Path, reviewer: str | None = None) -> dict:
    d = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
    lang = d["lang"]
    who = (reviewer or d.get("reviewer") or "").strip()
    if not who:
        raise SystemExit("name the reviewer: --reviewer 'Name' (it is recorded with each reviewed line)")
    doc = load(lang)
    counts = {"ok": 0, "fixed": 0, "needs_fix": 0, "unknown": 0}
    for src, dec in d["decisions"].items():
        item = doc["items"].get(src)
        if not item:
            counts["unknown"] += 1
            continue
        status = dec.get("status")
        text = normalize(dec.get("text") or "")
        if status in ("ok", "fixed") and text and text != item["text"]:
            if problems(lang, item["en"], text):
                status = "needs_fix"
            else:
                item["text"], status = text, "fixed"
        elif status == "fixed":
            status = "ok"
        if status not in ("ok", "fixed", "needs_fix"):
            continue
        item["status"], item["reviewer"], item["reviewed_on"] = status, who, time.strftime("%Y-%m-%d")
        counts[status] += 1
    save(doc)
    return counts


def clips(lang_filter: set[str] | None = None) -> list[dict]:
    """Manifest rows for every translated line that is not flagged needs_fix (status travels with the clip)."""
    out = []
    for p in sorted(TRANS_DIR.glob("*.json")) if TRANS_DIR.is_dir() else []:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if lang_filter and doc["lang"] not in lang_filter:
            continue
        for item in doc["items"].values():
            if item["status"] in IN_MANIFEST:
                out.append({"demo": item["demo"], "lang": doc["lang"], "text": item["text"], "status": item["status"]})
    return out


def status_table() -> list[tuple[str, dict]]:
    rows = []
    for p in sorted(TRANS_DIR.glob("*.json")) if TRANS_DIR.is_dir() else []:
        doc = json.loads(p.read_text(encoding="utf-8"))
        c = {s: 0 for s in STATUSES}
        for item in doc["items"].values():
            c[item["status"]] += 1
        rows.append((doc["lang"], c))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--langs", default=",".join(DEFAULT_LANGS), help=f"comma list; other demo languages: {','.join(OTHER_DEMO_LANGS)}")
        p.add_argument("--max-usd", type=float, default=1.0)
    sub.add_parser("status")
    rp = sub.add_parser("review-page")
    rp.add_argument("--lang", required=True)
    rp.add_argument("--out", required=True)
    ar = sub.add_parser("apply-review")
    ar.add_argument("decisions")
    ar.add_argument("--reviewer")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        for lang, c in status_table():
            print(f"{lang}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
        return 0
    if a.cmd == "review-page":
        Path(a.out).write_text(review_page(a.lang), encoding="utf-8")
        print(f"wrote {a.out}: open it in a browser, check each line, press 'Download my decisions'")
        return 0
    if a.cmd == "apply-review":
        print(json.dumps(apply_review(Path(a.decisions), a.reviewer)))
        return 0
    sources = english_sources()
    langs = [x for x in a.langs.split(",") if x]
    unknown = [x for x in langs if x not in LANG_NAMES]
    if unknown:
        print(f"no language name for {unknown}: add it to LANG_NAMES", file=sys.stderr)
        return 2
    todo = {lang: pending(lang, sources) for lang in langs}
    n = sum(len(v) for v in todo.values())
    cost = estimate(n) if n else 0.0
    print(f"{len(sources)} English lines; to translate: " + ", ".join(f"{k} {len(v)}" for k, v in todo.items())
          + f"; model {MODEL}; estimated ${cost:.2f} (worst case ${2 * cost:.2f}), cap ${a.max_usd:.2f}", flush=True)
    if a.cmd == "plan" or not n:
        return 0
    if cost > a.max_usd:
        print("estimate is above the cap: stopping", file=sys.stderr)
        return 2
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        print("XAI_API_KEY is not set: stopping", file=sys.stderr)
        return 2
    usage = {"in": 0, "out": 0, "calls": 0}
    failed: list[str] = []
    for lang, items in todo.items():
        if items:
            bad = translate_language(lang, items, key, usage)
            failed += [f"{lang}:{b}" for b in bad]
            spent = (usage["in"] * USD_PER_M_IN + usage["out"] * USD_PER_M_OUT) / 1e6
            print(f"{lang}: {len(items) - len(bad)}/{len(items)} ok{f', {len(bad)} failed' if bad else ''} | calls {usage['calls']} spent ${spent:.3f}", flush=True)
            if spent > a.max_usd:
                print("spend cap reached: stopping", file=sys.stderr)
                return 2
    print(json.dumps({"calls": usage["calls"], "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
