"""Blind listening panel: anonymized, randomized clips per sentence, a rating form, and an aggregator.

  python3 -m tts_bakeoff.panel build --out runs/2026-10-24 --langs km,vi --per-lang 8 --seed 7
      -> OUT/panel/panel_<lang>.html (give these to listeners), OUT/panel/key.json (keep private),
         OUT/panel/<lang>/<id>_<label>.wav (copies named by letter so file names do not reveal the model)
  python3 -m tts_bakeoff.panel aggregate --out runs/2026-10-24 ratings1.json ratings2.json ...
      -> OUT/panel/panel_results.csv with mean naturalness and intelligibility per model and language

Listeners rate every clip 1-5 on naturalness and on clarity, without knowing the model. Each listener downloads
a JSON file from the page and sends it back; nothing is uploaded anywhere. Use native speakers for each language.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sys
from pathlib import Path

LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

PAGE = """<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Listening panel: __LANG__</title>
<style>body{font:16px system-ui;max-width:820px;margin:1.5rem auto;padding:0 1rem}fieldset{margin:1rem 0;padding:.8rem;border-radius:8px}
.clip{display:grid;grid-template-columns:2rem 1fr;gap:.5rem;align-items:center;margin:.6rem 0}
.rate{display:flex;gap:1.2rem;flex-wrap:wrap;font-size:.9rem}.sent{font-size:1.1rem;margin:.2rem 0 .6rem}button{font-size:1rem;padding:.6rem 1rem}</style>
<h1>Listening panel (__LANG__)</h1>
<p>Listen to each clip. Rate how <b>natural</b> it sounds (1 robotic, 5 like a real teacher) and how <b>clear</b> it is (1 hard to understand, 5 perfectly clear). Clips are in random order and unlabeled by model.</p>
<label>Your name or id: <input id='rater' size='20'></label>
<div id='items'></div>
<p><button id='save'>Download my ratings</button> <span id='msg'></span></p>
<script>
const PANEL = __DATA__;
const items = document.getElementById('items');
for (const s of PANEL.sentences) {
  const fs = document.createElement('fieldset');
  fs.innerHTML = `<legend>${s.id}</legend><div class='sent'>${s.text}</div>` + s.clips.map(c => `
    <div class='clip'><b>${c.label}</b><div><audio controls preload='none' src='${c.src}'></audio>
    <div class='rate'><span>Natural: ${[1,2,3,4,5].map(n => `<label><input type='radio' name='nat-${s.id}-${c.label}' value='${n}'>${n}</label>`).join(' ')}</span>
    <span>Clear: ${[1,2,3,4,5].map(n => `<label><input type='radio' name='clr-${s.id}-${c.label}' value='${n}'>${n}</label>`).join(' ')}</span></div></div></div>`).join('');
  items.appendChild(fs);
}
document.getElementById('save').onclick = () => {
  const out = {panel: PANEL.panel_id, lang: PANEL.lang, rater: document.getElementById('rater').value || 'anonymous', ratings: []};
  let missing = 0;
  for (const s of PANEL.sentences) for (const c of s.clips) {
    const nat = document.querySelector(`input[name='nat-${s.id}-${c.label}']:checked`);
    const clr = document.querySelector(`input[name='clr-${s.id}-${c.label}']:checked`);
    if (!nat || !clr) { missing++; continue; }
    out.ratings.push({id: s.id, label: c.label, naturalness: +nat.value, clarity: +clr.value});
  }
  document.getElementById('msg').textContent = missing ? `${missing} clip(s) not rated yet; saved the rest.` : 'Saved. Please send the file back.';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'}));
  a.download = `ratings_${PANEL.lang}_${out.rater.replace(/[^a-z0-9]+/gi, '_')}.json`;
  a.click();
};
</script>"""


def build(out: Path, langs: list[str], per_lang: int, seed: int) -> dict:
    panel_dir = out / "panel"
    key: dict = {"seed": seed, "panels": {}}
    for lang in langs:
        by_id: dict[str, dict[str, Path]] = {}
        texts: dict[str, str] = {}
        for manifest in sorted(out.glob("*/manifest.jsonl")):
            model = manifest.parent.name
            for line in manifest.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                m = json.loads(line)
                if m.get("lang") == lang and m.get("status") == "ok" and (out / m["wav"]).exists():
                    by_id.setdefault(m["id"], {})[model] = out / m["wav"]
                    texts[m["id"]] = m["text"]
        # only sentences where at least two models have a clip, spread across categories by id order
        ids = [i for i in sorted(by_id) if len(by_id[i]) >= 2][:per_lang]
        if not ids:
            continue
        rng = random.Random(f"{seed}:{lang}")
        (panel_dir / lang).mkdir(parents=True, exist_ok=True)
        sentences, lang_key = [], {}
        for sid in ids:
            models = sorted(by_id[sid])
            rng.shuffle(models)
            clips = []
            for label, model in zip(LABELS, models):
                dest = panel_dir / lang / f"{sid}_{label}.wav"
                shutil.copyfile(by_id[sid][model], dest)
                clips.append({"label": label, "src": f"{lang}/{dest.name}"})
                lang_key[f"{sid}:{label}"] = model
            sentences.append({"id": sid, "text": texts[sid], "clips": clips})
        panel_id = f"{lang}-{seed}"
        data = {"panel_id": panel_id, "lang": lang, "sentences": sentences}
        html_text = PAGE.replace("__LANG__", lang).replace("__DATA__", json.dumps(data, ensure_ascii=False))
        (panel_dir / f"panel_{lang}.html").write_text(html_text, encoding="utf-8")
        key["panels"][panel_id] = lang_key
    (panel_dir / "key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    return key


def aggregate(out: Path, rating_files: list[Path]) -> list[dict]:
    key_path = out / "panel" / "key.json"
    key = json.loads(key_path.read_text(encoding="utf-8"))["panels"] if key_path.exists() else {}
    acc: dict[tuple[str, str], dict] = {}
    for f in rating_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        # Files exported by the listening lab (tts_bakeoff/lab) carry their own "id:label" -> model key.
        mapping = data.get("key") or key.get(data["panel"])
        if mapping is None:
            raise ValueError(f"{f}: unknown panel {data['panel']!r}")
        for r in data["ratings"]:
            model = mapping[f"{r['id']}:{r['label']}"]
            slot = acc.setdefault((data["lang"], model), {"nat": [], "clr": [], "raters": set()})
            slot["nat"].append(r["naturalness"])
            slot["clr"].append(r["clarity"])
            slot["raters"].add(data["rater"])
    rows = [{"lang": lang, "model": model, "ratings": len(v["nat"]), "raters": len(v["raters"]),
             "naturalness": round(sum(v["nat"]) / len(v["nat"]), 3), "clarity": round(sum(v["clr"]) / len(v["clr"]), 3)}
            for (lang, model), v in sorted(acc.items())]
    (out / "panel").mkdir(parents=True, exist_ok=True)
    with (out / "panel" / "panel_results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["lang", "model", "ratings", "raters", "naturalness", "clarity"])
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    b.add_argument("--langs", default="km,vi,th,es,en,zh,sw,hi")
    b.add_argument("--per-lang", type=int, default=8)
    b.add_argument("--seed", type=int, default=7)
    a = sub.add_parser("aggregate")
    a.add_argument("--out", required=True)
    a.add_argument("ratings", nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        key = build(Path(args.out), [x for x in args.langs.split(",") if x], args.per_lang, args.seed)
        print(f"built {len(key['panels'])} panel(s) in {Path(args.out) / 'panel'}; keep key.json private")
    else:
        for row in aggregate(Path(args.out), [Path(p) for p in args.ratings]):
            print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
