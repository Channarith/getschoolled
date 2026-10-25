"""A listening sheet for a native speaker to approve designed voices in a language, and the step that records her decisions.

  python3 -m tts_bakeoff.voice_design review-page --run RUN_DIR --lang yue [--out RUN_DIR/review-voices-yue.html]
      one self-contained HTML page (open it from the run folder, e.g. after rsync to the Mac: the audio is linked by relative path).
      For each voice, each tone and each method (designed in English / designed in Cantonese) the sentences play and she marks OK / not OK with a
      note. 'Download my decisions' saves review-voices-<lang>-decisions.json.
  python3 -m tts_bakeoff.voice_design apply-review decisions.json [--reviewer Wei]
      clears each voice for the language in tts_manifest/stock_voices.json: the voice needs its NEUTRAL variant marked OK (in either method);
      the cloning method is the Cantonese-designed one when that one is OK, else the English-designed one; the tones recorded are the ones
      marked OK under that method. A voice whose neutral variant is not OK is left uncleared (the note is kept in 'quality').
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from . import registry

LISTEN_FOR = {
    "yue": [
        "Tones: the line 詩、史、試、時、市、事 must give six clearly different words. Wrong tones change the meaning: mark Not OK.",
        "Naturalness: it sounds like spoken Cantonese, not Mandarin or an English speaker reading Cantonese. No English accent.",
        "Cute and anime: lively and sweet, but still an ADULT voice. Mark Not OK if it sounds like a child or a cartoon caricature.",
        "Same voice: gender and age as the name says, and the same speaker in every sentence. No hiss, clicks, cut-off or repeated syllables.",
    ],
}


def collect(run_dir: Path, lang: str) -> list[dict]:
    """[{voice, label, gender, tone, method, model, clips: [{id, category, text, wav}]}] for the designed voices that have clips in ``lang``."""
    run_dir = Path(run_dir)
    rows = []
    for meta_path in sorted(run_dir.glob("voxcpm2-design~*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        folder = meta_path.parent
        clips = []
        mf = folder / "manifest.jsonl"
        for line in (mf.read_text(encoding="utf-8").splitlines() if mf.is_file() else []):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("lang") == lang and r.get("status") == "ok" and r.get("wav"):
                clips.append({"id": r["id"], "text": r.get("text", ""), "wav": r["wav"]})
        if clips:
            rows.append({"voice": meta["stock"], "label": meta.get("label", meta["stock"]), "gender": meta.get("gender", ""), "tone": meta.get("tone", registry.NEUTRAL),
                         "method": meta.get("method", "en-ref"), "model": meta["model"], "clips": clips})
    return rows


def page(run_dir: Path, lang: str = "yue") -> str:
    rows = collect(run_dir, lang)
    if not rows:
        raise SystemExit(f"no designed-voice clips in {lang} under {run_dir}: run the grid first")
    voices: dict[str, dict] = {}
    for r in rows:
        v = voices.setdefault(r["voice"], {"label": r["label"].split(" · ")[0], "gender": r["gender"], "cells": {}})
        v["cells"][(r["tone"], r["method"])] = r
    tones = [t for t in [registry.NEUTRAL, *registry.TONES_ORDER] if any(t == k[0] for v in voices.values() for k in v["cells"])]
    methods = [m for m in registry.METHODS if any(m == k[1] for v in voices.values() for k in v["cells"])]
    esc = html.escape
    out = []
    for vid, v in voices.items():
        out.append(f"<section><h2>{esc(v['label'])} <small>{esc(v['gender'])} · {esc(vid)}</small></h2><div class='grid'>")
        for tone in tones:
            for method in methods:
                cell = v["cells"].get((tone, method))
                if not cell:
                    continue
                key = f"{vid}|{tone}|{method}"
                title = f"{tone} · {'designed in Cantonese' if method == 'yue-ref' else 'designed in English'}"
                players = "".join(
                    f"<div class='clip'><span class='t'>{esc(c['id'])}</span> <audio controls preload='none' src=\"{esc(c['wav'])}\"></audio>"
                    f"<div class='tx'>{esc(c['text'])}</div></div>" for c in cell["clips"])
                out.append(
                    f"<div class='cell' data-key=\"{esc(key)}\"><h3>{esc(title)}</h3>{players}"
                    f"<label><input type='radio' name=\"{esc(key)}\" value='ok'> OK 可以</label> "
                    f"<label><input type='radio' name=\"{esc(key)}\" value='not_ok'> Not OK 唔得</label> "
                    f"<input class='note' placeholder='note 備註' data-note=\"{esc(key)}\"></div>")
        out.append("</div></section>")
    listen = "".join(f"<li>{esc(x)}</li>" for x in LISTEN_FOR.get(lang, []))
    return PAGE.replace("@LANG@", esc(lang)).replace("@LISTEN@", listen).replace("@BODY@", "\n".join(out))


PAGE = """<!doctype html><meta charset="utf-8"><title>Voice review (@LANG@)</title>
<style>body{font:16px system-ui;margin:1.2rem auto;max-width:1100px;padding:0 1rem;background:#faf7f0;color:#222}
h2 small{font-weight:400;color:#777;font-size:.7em}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:.8rem}
.cell{background:#fff;border:1px solid #d9c9a3;border-radius:10px;padding:.7rem}.cell h3{margin:.1rem 0 .5rem;font-size:1rem}
.clip{margin:.3rem 0}.clip audio{width:100%;height:34px}.tx{font-size:.85rem;color:#555}.t{font-weight:600}.note{width:100%;margin-top:.4rem}
button{font-size:1rem;padding:.5rem 1rem;margin:.5rem 0}.done{background:#e8f5e9}</style>
<h1>Voice review: @LANG@</h1>
<p>Listen to each voice and mark OK or Not OK. Skip anything you are not sure about. Then press <b>Download my decisions</b> and send the file back.</p>
<ul>@LISTEN@</ul>
<label>Your name <input id="who" value="Wei"></label>
@BODY@
<button id="dl">Download my decisions</button>
<script>
document.querySelectorAll('.cell').forEach(c=>c.querySelectorAll('input[type=radio]').forEach(r=>r.onchange=()=>c.classList.add('done')));
document.getElementById('dl').onclick=()=>{
  const decisions=[];
  document.querySelectorAll('.cell').forEach(c=>{
    const key=c.dataset.key, sel=c.querySelector('input[type=radio]:checked'), note=c.querySelector('.note').value.trim();
    if(!sel&&!note) return;
    const [voice,tone,method]=key.split('|');
    decisions.push({voice,tone,method,status:sel?sel.value:'unsure',note});
  });
  const blob=new Blob([JSON.stringify({lang:'@LANG@',reviewer:document.getElementById('who').value.trim(),decisions},null,1)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='review-voices-@LANG@-decisions.json';a.click();
};
</script>"""


def apply(decisions_path: Path, reviewer: str | None = None, path: Path = registry.STOCK, today: str | None = None) -> dict:
    doc = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
    lang, who = doc["lang"], (reviewer or doc.get("reviewer") or "").strip()
    if not who:
        raise registry.StockError("apply-review needs a reviewer name (--reviewer or the name typed in the page)")
    by_voice: dict[str, list[dict]] = {}
    for d in doc["decisions"]:
        by_voice.setdefault(d["voice"], []).append(d)
    summary = {"cleared": {}, "not_cleared": [], "reviewer": who, "lang": lang}
    for vid, ds in by_voice.items():
        ok = {(d["tone"], d["method"]) for d in ds if d["status"] == "ok"}
        notes = "; ".join(f"{d['tone']}/{d['method']}: {d['note']}" for d in ds if d.get("note"))
        method = next((m for m in ("yue-ref", "en-ref") if (registry.NEUTRAL, m) in ok), None)
        if method is None:
            summary["not_cleared"].append(vid)
            if notes:
                entry = registry.load(path)
                e = next(v for v in entry["voices"] if v["id"] == vid)
                e.setdefault("quality", {})[lang] = f"not cleared by {who}: {notes}"
                registry.save(entry, path)
            continue
        tones = sorted({t for t, m in ok if m == method and t != registry.NEUTRAL}, key=lambda t: list(registry.TONES_ORDER).index(t))
        registry.clear(vid, lang, who, tones=tones, method=method, note=notes, path=path, today=today)
        summary["cleared"][vid] = {"method": method, "tones": tones}
    return summary
