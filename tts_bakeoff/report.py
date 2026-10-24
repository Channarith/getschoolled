"""Leaderboard per language from scored runs: one HTML page plus a CSV, with a license / shippable column.

  python3 -m tts_bakeoff.report --out runs/2026-10-24

Ranking within a language is by mean ASR round-trip error (lower is better). That is intelligibility only:
read it next to the listening-panel results. Models that are not shippable are shown, clearly marked, as
internal references and are never recommended for the product.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import statistics
import sys
from pathlib import Path

from . import schema

ADAPTER_TO_CANDIDATE = {}


def candidate_for(model: str, cands: dict[str, dict]) -> dict:
    for c in cands.values():
        if c.get("adapter") == model:
            return c
    return {"id": model, "name": model, "role": "unknown", "license": {}, "languages": []}


def load_scores(out: Path) -> list[dict]:
    rows = []
    for path in sorted(out.glob("*/scores.jsonl")):
        latest = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                latest[(r["lang"], r["id"])] = r  # a later row for the same clip replaces an earlier one
        rows.extend(latest.values())
    return rows


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def summarize(rows: list[dict], cands: dict[str, dict]) -> dict[str, list[dict]]:
    by: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        if "error" in r:
            by.setdefault((r["lang"], r["model"]), []).append(r)
    table: dict[str, list[dict]] = {}
    for (lang, model), rs in by.items():
        errs = [r["error"]["value"] for r in rs]
        rtfs = [r["rtf"] for r in rs if r.get("rtf")]
        nat = [r["naturalness"] for r in rs if r.get("naturalness") is not None]
        flags = sum(1 for r in rs if r.get("audio", {}).get("flags"))
        cand = candidate_for(model, cands)
        table.setdefault(lang, []).append({
            "lang": lang, "model": model, "name": cand.get("name", model), "metric": rs[0]["error"]["metric"].upper(),
            "n": len(rs), "mean_error": statistics.mean(errs), "p90_error": pct(errs, 0.9),
            "mean_rtf": statistics.mean(rtfs) if rtfs else None, "mean_naturalness": statistics.mean(nat) if nat else None,
            "flagged_clips": flags, "digits_ignored": sum(1 for r in rs if r["error"].get("digits_ignored")),
            "license": schema.label(cand) if cand.get("license") else "UNKNOWN", "role": cand.get("role", "unknown"),
            "asr": rs[0].get("asr"),
        })
    for lang in table:
        table[lang].sort(key=lambda r: r["mean_error"])
    return table


def write_csv(table: dict[str, list[dict]], path: Path) -> None:
    fields = ["lang", "rank", "model", "name", "license", "role", "metric", "mean_error", "p90_error", "n", "mean_rtf", "mean_naturalness", "flagged_clips", "digits_ignored", "asr"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for lang in sorted(table):
            for i, r in enumerate(table[lang], 1):
                w.writerow({**r, "rank": i})


def render_html(table: dict[str, list[dict]]) -> str:
    parts = ["<!doctype html><meta charset='utf-8'><title>TTS bake-off leaderboard</title>",
             "<style>body{font:15px system-ui;margin:2rem;max-width:1100px}table{border-collapse:collapse;margin:.5rem 0 2rem;width:100%}"
             "th,td{border:1px solid #ccc;padding:.35rem .6rem;text-align:left}th{background:#f3f3f3}"
             ".ok{color:#0a6b2a;font-weight:700}.no{color:#a11;font-weight:700}.chk{color:#8a5a00;font-weight:700}</style>",
             "<h1>TTS bake-off leaderboard</h1><p>Ranked by mean ASR round-trip error per language (lower is better). "
             "Intelligibility only: read with the listening panel. NOT SHIPPABLE models are internal references.</p>"]
    for lang in sorted(table):
        parts.append(f"<h2>{html.escape(lang)}</h2><table><tr><th>#</th><th>model</th><th>license</th><th>role</th><th>error</th><th>p90</th><th>clips</th><th>RTF</th><th>naturalness</th><th>flagged</th><th>ASR</th></tr>")
        for i, r in enumerate(table[lang], 1):
            cls = {"SHIPPABLE": "ok", "NOT SHIPPABLE": "no"}.get(r["license"], "chk")
            nat = f"{r['mean_naturalness']:.2f}" if r["mean_naturalness"] is not None else "-"
            rtf = f"{r['mean_rtf']:.2f}" if r["mean_rtf"] is not None else "-"
            note = f" ({r['digits_ignored']} with digits ignored)" if r["digits_ignored"] else ""
            parts.append(
                f"<tr><td>{i}</td><td>{html.escape(r['name'])}</td><td class='{cls}'>{html.escape(r['license'])}</td><td>{html.escape(r['role'])}</td>"
                f"<td>{r['metric']} {100 * r['mean_error']:.1f}%{html.escape(note)}</td><td>{100 * r['p90_error']:.1f}%</td><td>{r['n']}</td><td>{rtf}</td><td>{nat}</td><td>{r['flagged_clips']}</td><td>{html.escape(str(r['asr']))}</td></tr>")
        parts.append("</table>")
    return "".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    out = Path(args.out)
    table = summarize(load_scores(out), schema.candidates())
    if not table:
        print("no scores found; run score_bakeoff first")
        return 1
    write_csv(table, out / "leaderboard.csv")
    (out / "leaderboard.html").write_text(render_html(table), encoding="utf-8")
    print(f"wrote {out / 'leaderboard.html'} and leaderboard.csv for {len(table)} languages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
