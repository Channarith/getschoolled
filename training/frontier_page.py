"""The long frontier briefing. Numbers come from the snapshot. The three
historical charts are the measured series through 22 Oct 2026, 5 AM PT.
"""

from __future__ import annotations

import html
from pathlib import Path

TRAINING_FLOOR = 0.40
ACCREDITATION_FLOOR = 0.70
TARGET_FROZEN = 0.70
TARGET_GROUNDEDNESS = 0.90

_CSS = """
  :root { color-scheme: dark; }
  body { margin:0; background:#0e141b; color:#e7ecf1; font:16px/1.45 "Iowan Old Style", Palatino, "Palatino Linotype", serif; }
  header, main { max-width:1080px; margin:0 auto; padding:28px 22px 8px; }
  h1 { font-weight:650; font-size:34px; letter-spacing:-0.03em; margin:0 0 8px; }
  h2 { font-size:22px; margin:36px 0 8px; letter-spacing:-0.02em; }
  h3 { font-size:16px; margin:0 0 6px; font-weight:650; }
  p, li { margin:8px 0; }
  ol { padding-left:1.2em; }
  ol li { margin:12px 0; }
  .lede { font-size:18px; max-width:74ch; color:#d5dee6; }
  .meta { color:#8b98a5; font:13px/1.4 ui-sans-serif, system-ui, sans-serif; }
  .grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-top:18px; }
  .card { background:#161d26; border:1px solid #2a3542; border-radius:14px; padding:14px 14px 12px; }
  .card b { display:block; font:22px/1.1 ui-sans-serif, system-ui, sans-serif; letter-spacing:-0.03em; }
  .card span, .note, figcaption, td, th, ol li { font:13px/1.4 ui-sans-serif, system-ui, sans-serif; }
  .card span, .note, figcaption { color:#8b98a5; }
  .ok { color:#8ee0c8; } .warn { color:#e6b35a; } .bad { color:#f0a598; }
  .row { display:grid; grid-template-columns:1.2fr .8fr; gap:16px; align-items:start; }
  figure { margin:12px 0; background:#121920; border:1px solid #2a3542; border-radius:14px; padding:12px; }
  svg { width:100%; height:auto; }
  .legend { display:flex; gap:16px; flex-wrap:wrap; color:#c5d0da; font:12px/1 ui-sans-serif, system-ui, sans-serif; margin:4px 0 8px; }
  .sw { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-1px; }
  .donuts { display:flex; flex-wrap:wrap; gap:8px; }
  .donut { width:168px; text-align:center; }
  .donut p { color:#8b98a5; font:12px/1.35 ui-sans-serif, system-ui, sans-serif; margin:0; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:8px 8px; border-bottom:1px solid #2a3542; vertical-align:top; }
  th { color:#8b98a5; font-weight:600; }
  .scene { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .flow { display:flex; flex-wrap:wrap; gap:8px; align-items:stretch; }
  .step { flex:1 1 120px; background:#1a222c; border:1px solid #2c3a48; border-radius:12px; padding:10px; }
  .step b { display:block; font:14px/1.2 ui-sans-serif, system-ui, sans-serif; margin-bottom:6px; }
  .step p { margin:0; color:#c5d0da; font:12px/1.35 ui-sans-serif, system-ui, sans-serif; }
  .step em { display:block; margin-top:8px; color:#e6b35a; font-style:normal; font:12px/1.3 ui-sans-serif, system-ui, sans-serif; }
  .kicker { font:12px/1 ui-sans-serif, system-ui, sans-serif; letter-spacing:.14em; text-transform:uppercase; color:#3dbea5; }
  .bar { position:relative; height:10px; background:#243140; border-radius:6px; }
  .bar span { display:block; height:10px; border-radius:6px; }
  .bar i { position:absolute; top:-2px; width:2px; height:14px; background:#e6b35a; }
  footer { max-width:1080px; margin:0 auto; padding:8px 22px 40px; color:#8b98a5; font:12px/1.4 ui-sans-serif, system-ui, sans-serif; }
  code { font:12px/1.4 ui-monospace, monospace; }
  @media (max-width:800px) { .grid,.row,.scene { grid-template-columns:1fr; } }
"""


def _pct(value) -> str:
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


def _donut(fraction: float, label: str, caption: str, color: str) -> str:
    circ = 339.29
    fraction = max(0.0, min(1.0, fraction))
    dash = fraction * circ
    rest = circ - dash
    return (
        '<div class="donut"><svg viewBox="0 0 140 140" width="140" height="140">'
        '<circle cx="70" cy="70" r="54" fill="none" stroke="#243140" stroke-width="12"/>'
        f'<circle cx="70" cy="70" r="54" fill="none" stroke="{color}" stroke-width="12" '
        f'stroke-linecap="round" stroke-dasharray="{dash:.2f} {rest:.2f}" '
        'transform="rotate(-90 70 70)"/>'
        f'<text x="70" y="66" text-anchor="middle" fill="#e7ecf1" font-size="22" font-weight="650">{fraction * 100:.0f}%</text>'
        f'<text x="70" y="86" text-anchor="middle" fill="#8b98a5" font-size="11">{html.escape(label)}</text>'
        f'</svg><p>{html.escape(caption)}</p></div>'
    )


def _bar(score: float, floor: float) -> str:
    width = max(0, min(100, score * 100))
    color = "#e07a6a" if score < 0.20 else "#e6b35a" if score < floor else "#3dbea5"
    return (
        f'<div class="bar"><span style="width:{width:.1f}%;background:{color}"></span>'
        f'<i style="left:{floor * 100:.1f}%"></i></div>'
    )


def _subject_chart(rows: list[dict]) -> str:
    if not rows:
        return "<p>No subject rows yet.</p>"
    width = 40 + len(rows) * 36
    base_y = 480
    top = 70
    span = base_y - top
    y70 = base_y - ACCREDITATION_FLOOR * span
    y40 = base_y - TRAINING_FLOOR * span
    parts = [
        f'<svg viewBox="0 0 {width} 560" role="img" aria-label="Accuracy by subject">',
        f'<line x1="36" y1="{y70:.1f}" x2="{width - 16}" y2="{y70:.1f}" stroke="#e07a6a" stroke-dasharray="4 3"/>',
        f'<text x="{width - 16}" y="{y70 - 4:.1f}" fill="#e07a6a" font-size="11" text-anchor="end">70% accreditation floor</text>',
        f'<line x1="36" y1="{y40:.1f}" x2="{width - 16}" y2="{y40:.1f}" stroke="#e6b35a" stroke-dasharray="4 3"/>',
        f'<text x="{width - 16}" y="{y40 - 4:.1f}" fill="#e6b35a" font-size="11" text-anchor="end">40% training floor</text>',
    ]
    for i, row in enumerate(rows):
        score = float(row["score"])
        bar_h = max(2.0, score * span)
        x = 40 + i * 36
        y = base_y - bar_h
        color = "#e07a6a" if score < 0.20 else "#e6b35a" if score < TRAINING_FLOOR else "#3dbea5"
        label = html.escape(str(row["subject"]))
        parts.append(
            f'<rect x="{x}" y="{y:.1f}" width="22" height="{bar_h:.1f}" fill="{color}" rx="3"/>'
            f'<text x="{x + 11}" y="{y - 4:.1f}" fill="#c5d0da" font-size="9" text-anchor="middle">{score * 100:.0f}%</text>'
            f'<text x="{x + 11}" y="540" fill="#8b98a5" font-size="10" text-anchor="end" '
            f'transform="rotate(-55 {x + 11} 540)">{label}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _lang_bars(rows: list[dict]) -> str:
    if not rows:
        return "<p>Translation cache was not scanned.</p>"
    height = 28 * len(rows) + 8
    parts = [f'<svg viewBox="0 0 760 {height}" role="img" aria-label="Playable translations by language">']
    for i, row in enumerate(rows):
        y = 6 + i * 28
        total = row["total"] or 1
        width = 420 * (row["playable"] / total)
        parts.append(
            f'<text x="0" y="{y + 14}" fill="#c5d0da" font-size="12">{html.escape(row["code"])}</text>'
            f'<rect x="48" y="{y}" width="420" height="16" fill="#243140" rx="3"/>'
            f'<rect x="48" y="{y}" width="{width:.1f}" height="16" fill="#3dbea5" rx="3"/>'
            f'<text x="478" y="{y + 14}" fill="#8b98a5" font-size="12">'
            f'{row["playable"]} playable / {row["total"]}, {row["partial"]} partial</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _history_chart(history: list[dict]) -> str:
    points = [row for row in history if row.get("frozen_accuracy") is not None]
    if len(points) < 2:
        return "<p>Not enough recorded rows yet to draw the frozen-score line.</p>"
    points = points[-12:]
    width = 920
    left, right = 48, 904
    top, bottom = 18, 250
    span = bottom - top

    def xy(i: int, value: float) -> str:
        x = left + (right - left) * i / (len(points) - 1)
        y = bottom - max(0.0, min(0.40, float(value))) / 0.40 * span
        return f"{x:.1f},{y:.1f}"

    frozen = " ".join(xy(i, row["frozen_accuracy"]) for i, row in enumerate(points))
    split_bits = []
    for i, row in enumerate(points):
        if row.get("split_accuracy") is not None:
            split_bits.append(xy(i, row["split_accuracy"]))
    labels = []
    for i, row in enumerate(points):
        if i in {0, len(points) // 2, len(points) - 1}:
            x = left + (right - left) * i / (len(points) - 1)
            labels.append(
                f'<text x="{x:.1f}" y="286" fill="#8b98a5" font-size="11" text-anchor="middle">'
                f'{html.escape(str(row.get("at")))}</text>'
            )
    grid = []
    for tick in (0.10, 0.20, 0.30, 0.40):
        y = bottom - tick / 0.40 * span
        grid.append(
            f'<line x1="48" y1="{y:.1f}" x2="904" y2="{y:.1f}" stroke="#2a3542"/>'
            f'<text x="40" y="{y + 4:.1f}" fill="#8b98a5" font-size="11" text-anchor="end">{tick * 100:.0f}%</text>'
        )
    split_line = ""
    if len(split_bits) == len(points):
        split_line = f'<polyline fill="none" stroke="#3dbea5" stroke-width="2.2" points="{" ".join(split_bits)}"/>'
    return (
        '<svg viewBox="0 0 920 300" role="img" aria-label="Frozen exam score across recorded snapshots">'
        + "".join(grid)
        + split_line
        + f'<polyline fill="none" stroke="#7aa2ff" stroke-width="2.2" points="{frozen}"/>'
        + "".join(labels)
        + "</svg>"
    )


def _historical_figures() -> list[str]:
    path = Path(__file__).with_name("frontier_history_figures.html")
    if not path.is_file():
        return []
    return [part.strip() for part in path.read_text(encoding="utf-8").split("<!-- FIG -->") if part.strip()]


def _subject_table(rows: list[dict]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr><td>" + html.escape(str(row["subject"])) + "</td><td>" + _pct(row["score"])
            + "</td><td>" + str(row["n"]) + "</td><td>" + _bar(float(row["score"]), TRAINING_FLOOR) + "</td></tr>"
        )
    return "".join(body) or "<tr><td colspan=4>No rows yet.</td></tr>"


def render_briefing(snapshot: dict, history: list[dict]) -> str:
    e = html.escape
    truth = snapshot.get("truth") or {}
    translation = snapshot.get("translation") or {}
    batch = snapshot.get("batch") or {}
    weak = snapshot.get("weakest_split") or {}
    frozen_weak = snapshot.get("weakest_frozen") or {}
    stem_weak = snapshot.get("weakest_stem") or {}
    languages = translation.get("languages") or []
    demo = translation.get("demo") or {}
    demo_bits = ", ".join(
        f"{e(code)} {e(state)}" for code, state in demo.items() if state != "playable"
    ) or "all playable"
    courses = int(translation.get("courses") or 0)
    yue_playable = int(translation.get("yue_playable") or 0)
    yue_partial = int(translation.get("yue_partial") or 0)
    done = int(batch.get("done") or 0)
    total = int(batch.get("total") or 0)
    written = int(batch.get("written") or 0)
    skipped = int(batch.get("skipped") or 0)
    failed = int(batch.get("failed") or 0)
    frozen = snapshot.get("frozen_accuracy")
    split = snapshot.get("split_accuracy")
    stem = snapshot.get("stem_accuracy")
    batch_fraction = (done / total) if total else 0.0
    yue_fraction = (yue_playable / courses) if courses else 0.0
    frozen_of_target = (float(frozen) / TARGET_FROZEN) if frozen is not None else 0.0
    split_of_target = (float(split) / TARGET_FROZEN) if split is not None else 0.0
    demo_playable = sum(1 for state in demo.values() if state == "playable")
    demo_fraction = (demo_playable / len(demo)) if demo else 0.0
    algebra = None
    for row in snapshot.get("stem_subjects") or []:
        if row["subject"] == "linear-algebra":
            algebra = row["score"]
    figures = _historical_figures()
    tutor_fig = figures[0] if len(figures) > 0 else ""
    fair_fig = figures[1] if len(figures) > 1 else ""
    khmer_fig = figures[2] if len(figures) > 2 else ""
    hist_rows = []
    for row in history[-12:]:
        hist_rows.append(
            "<tr><td>" + e(str(row.get("at"))) + "</td><td>" + _pct(row.get("frozen_accuracy"))
            + "</td><td>" + _pct(row.get("split_subject_min")) + "</td><td>"
            + _pct(row.get("groundedness")) + "</td><td>" + str(row.get("yue_playable"))
            + "</td><td>" + e(str(row.get("promote_reason") or "")) + "</td></tr>"
        )
    algebra_n = (snapshot.get("stem_exam_subjects") or {}).get("linear-algebra", 0)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Salareen frontier readiness — {e(snapshot["at"])}</title>
<style>{_CSS}</style>
</head>
<body>
<header>
  <div class="kicker">Salareen · measured on Chans-Spark</div>
  <h1>Where the model stands, and what still blocks a frontier tutor.</h1>
  <p class="lede">The frozen exam is now the score that counts, and it is stuck at {_pct(frozen)}. The adapter still beats the base on the 41-item split ({_pct(split)} versus {_pct(snapshot.get("split_base"))}), and the gate refuses to keep it. Cantonese text exists for {yue_playable} of {courses} courses. The demo lesson still speaks English. Nothing in this stack yet earns an outside credential.</p>
  <p class="meta">Snapshot {e(snapshot["at"])}. Rebuild with <code>python3 training/frontier_readiness.py --record</code> from the spark-eval-gates tree. Scores are token-overlap F1 unless a row says otherwise. Proposed bars are targets, drawn next to measurements so the gap is visible. They are not results.</p>
</header>
<main>
  <section class="grid">
    <div class="card"><b>{_pct(frozen)}</b><span>Adapter on the frozen 200-item exam. Base {_pct(snapshot.get("frozen_base"))}. Target {_pct(TARGET_FROZEN)}. Weakest subject: {e(str(frozen_weak.get("subject") or "—"))} {_pct(frozen_weak.get("score"))}.</span></div>
    <div class="card"><b>{_pct(split)}</b><span>STEM adapter on the 41-item split. Base {_pct(snapshot.get("split_base"))}. Weakest sampled subject: {e(str(weak.get("subject") or "—"))} {_pct(weak.get("score"))}. This number has not moved.</span></div>
    <div class="card"><b class="warn">{_pct(stem)}</b><span>Adapter on the frozen STEM exam ({snapshot.get("stem_exam_items")} items, linear algebra n={algebra_n}). Weakest subject: {e(str(stem_weak.get("subject") or "—"))} {_pct(stem_weak.get("score"))}.</span></div>
    <div class="card"><b class="bad">{snapshot.get("cards", 0)}</b><span>Outside cards. A person of record and a {ACCREDITATION_FLOOR:.0%} subject floor are required even to ask. Salareen does not print the card.</span></div>
  </section>

  <h2>What is running now</h2>
  <div class="row">
    <div>
      <p>As of this snapshot the STEM shell is still the systemd service, and it is not scoring. The last finished cycle wrote its result at 4:55 AM PT and refused promotion. The bake-off winner was <code>{e(str(snapshot.get("promote_champion") or "none"))}</code> at {_pct(snapshot.get("served_accuracy"))} on {snapshot.get("served_n") or "—"} frozen items, fairness gap {_pct(snapshot.get("served_gap"))}. That score was not kept. The adapter stayed {_pct(frozen)}. Gate: <code>{e(str(snapshot.get("promote_reason") or "not run yet"))}</code>. Promoted: {e(str(snapshot.get("promoted")))}. Khmer CosyVoice is off, and the hold file is still there.</p>
      <p>Translation is stopped. The unit was disabled at 2:26 AM PT Saturday, and the NLLB server on port 8002 is down. {e(f"Last tally {done}/{total}: written {written}, skipped {skipped}, failed {failed}.") if total else "The batch log has no progress line yet."} Most of those failures are empty translations after the gateway refused connections. The batch does not resume on its own while the unit stays disabled.</p>
    </div>
    <div class="card">
      <h3>Why the loop is flat</h3>
      <p>Each cycle fine-tunes the same 373 examples for one epoch, then scores the frozen 200, the 96-item STEM exam, and the 41-item split. The frozen result stays {_pct(frozen)}. The split stays {_pct(split)}. Fairness gap on the frozen exam is {_pct(snapshot.get("frozen_gap"))}. On the split it is {_pct(snapshot.get("split_gap"))}. The subject floor is {TRAINING_FLOOR:.0%}. Health &amp; Wellness, calculus 1, and the Python files item are all under it.</p>
    </div>
  </div>

  <h2>How much is done</h2>
  <div class="donuts">
    {_donut(frozen_of_target, "of 70%", f"Frozen exam versus a 70% tutor bar. {_pct(frozen)} / 70%.", "#e6b35a")}
    {_donut(split_of_target, "of 70%", f"Split score versus that same 70% bar. {_pct(split)} / 70%. The split itself is unchanged.", "#3dbea5")}
    {_donut(batch_fraction, "of batch", f"222-course jobs reached. {done} / {total}. Written {written}, failed {failed}.", "#e6b35a")}
    {_donut(yue_fraction, "Cantonese", f"Playable yue.json files. {yue_playable} / {courses}. Partials: {yue_partial}.", "#3dbea5" if yue_playable else "#e07a6a")}
    {_donut(demo_fraction, "demo", "Demo lesson languages the app can speak. Wrong-length files are refused, so English plays.", "#e07a6a")}
    {_donut(0.0, "cards", "External certificates this code path can issue today.", "#e07a6a")}
    {_donut(float(truth.get("groundedness") or 0), "grounded", f"Mean groundedness on {truth.get('n', 0)} logged rows. Target 90%.", "#e6b35a")}
    {_donut(float(truth.get("abstain_accuracy") or 0), "abstain", "Abstention accuracy on those rows. Human agreement is still empty.", "#7aa2ff")}
  </div>
  <p class="note">Percent rings are progress toward the named bar, not a single model score. A ring at 29% of 70% means the frozen exam is {_pct(frozen)}.</p>

  <h2>Time series — the tutor score is flat</h2>
  <figure>
    <figcaption>Recorded snapshots, Pacific time. Blue is the frozen 200-item exam. Teal, when present, is the 41-item split. The Y-axis stops at 40% so a stuck line is readable. A frontier tutor is not this chart.</figcaption>
    <div class="legend"><span><i class="sw" style="background:#7aa2ff"></i>frozen exam</span><span><i class="sw" style="background:#3dbea5"></i>41-item split</span></div>
    {_history_chart(history)}
  </figure>
  <p>The earlier serve-eval, through 5 AM PT on 22 Oct, is below. Teal was the STEM adapter, flat at 31.5%. Gray was the base at 12.1%. Blue was the served 35B on that same small overlap check. That series is not the live score. The live score is the frozen exam in the chart above.</p>
  {tutor_fig}
  {fair_fig}
  <p>Inference: the nightly job is still rescoring one adapter. The frozen exam stopped the false promotion. It did not raise the score. A real gain is a higher frozen number, with every subject at or above {TRAINING_FLOOR:.0%}. That has not happened.</p>

  <h2>Khmer voice — eight epochs, then held</h2>
  <p>The last full Khmer pass finished 8 of 8 epochs and was not promoted. Dev loss ran from 3.40 to 2.94, and speech-token accuracy ended at 27.4% on epoch 7. That pass is not what a learner hears. The voice job is off, and it must not be started again from <code>CosyVoice-300M/llm.pt</code> while this exam needs the GPU. Edge voices already speak playback: Mandarin Xiaoxiao / Yunxi, Cantonese HiuMaan, Khmer Sreymom / Piseth. They need lesson text of the right length. They are not a fine-tuned Salareen voice.</p>
  {khmer_fig}

  <h2>Subject dependency — the spread is the bias that matters</h2>
  <figure>
    <figcaption>Adapter token-overlap by subject on the 41-item split. Red is under 20%. Gold is under the 40% training floor. Teal clears that floor and still sits under the 70% accreditation line. The fairness gap compares audience groups. It does not excuse a weak subject. Linear algebra on this split is {_pct(weak.get("score") if weak.get("subject") == "linear-algebra" else next((r["score"] for r in snapshot.get("split_subjects") or [] if r["subject"] == "linear-algebra"), None))}.</figcaption>
    {_subject_chart(snapshot.get("split_subjects") or [])}
  </figure>
  <table>
    <tr><th>Subject</th><th>Score</th><th>Items</th><th>Against the 40% floor</th></tr>
    {_subject_table(snapshot.get("split_subjects") or [])}
  </table>
  <h3>Frozen STEM exam, 4 items each</h3>
  <p>Linear algebra on this exam is {_pct(algebra)}. The weakest STEM subject is {e(str(stem_weak.get("subject") or "—"))} at {_pct(stem_weak.get("score"))}. The frozen general exam’s weakest subject is {e(str(frozen_weak.get("subject") or "—"))} at {_pct(frozen_weak.get("score"))}. A credential is only as strong as that row.</p>
  <figure>
    {_subject_chart(snapshot.get("stem_subjects") or [])}
  </figure>

  <h2>Truth curve</h2>
  <div class="row">
    <figure>
      <figcaption>Target curve in teal: when the tutor says it is 80% sure, about 80% of those claims should be true. The dashed red bow is an illustration of overconfidence, not a fit. Human agreement is still empty, so this is not yet a measured curve.</figcaption>
      <svg viewBox="0 0 420 260" role="img" aria-label="Target truth curve versus an overconfident illustration">
        <line x1="40" y1="210" x2="360" y2="210" stroke="#8b98a5"/>
        <line x1="40" y1="210" x2="40" y2="30" stroke="#8b98a5"/>
        <polyline fill="none" stroke="#3dbea5" stroke-width="2.4" points="40,210.0 72,193.0 104,176.0 136,159.0 168,142.0 200,125.0 232,108.0 264,91.0 296,74.0 328,57.0 360,40.0"/>
        <polyline fill="none" stroke="#e07a6a" stroke-width="2.2" stroke-dasharray="5 4" points="40,210.0 72,205.7 104,197.1 136,185.2 168,170.8 200,153.9 232,134.9 264,113.9 296,91.0 328,66.4 360,40.0"/>
        <text x="200" y="242" fill="#8b98a5" font-size="12" text-anchor="middle">claimed confidence</text>
        <text x="16" y="120" fill="#8b98a5" font-size="12" transform="rotate(-90 16 120)">share of claims that were true</text>
        <text x="200" y="22" fill="#3dbea5" font-size="12" text-anchor="middle">target: say 80% only when 80% are true</text>
      </svg>
    </figure>
    <div>
      <p>Logged rows now carry groundedness and abstention. Mean groundedness is {_pct(truth.get("groundedness"))} on {truth.get("n", 0)} rows. Abstention accuracy is {_pct(truth.get("abstain_accuracy"))}. Human agreement is {_pct(truth.get("human_agreement"))} from {truth.get("human_n", 0)} reviews.</p>
      <p>The code that stands in for the curve is <code>check_grounding</code>. A claim needs support of at least 0.50. The answer passes when at least 70% of claims clear that bar. Otherwise the tutor is supposed to abstain and quote the lesson. Token overlap can mark a reworded true sentence as unsupported, and a fluent false sentence as supported when the words match. The missing mark is whether a person later agreed.</p>
      <table>
        <tr><th>Mark</th><th>Today</th><th>Accredited bar</th></tr>
        <tr><td>Claim support</td><td>0.50 overlap to count</td><td>Keep a lexical floor, add a human-checked subset</td></tr>
        <tr><td>Answer pass</td><td>70% of claims</td><td>90% of claims, else abstain</td></tr>
        <tr><td>Abstention</td><td>{_pct(truth.get("abstain_accuracy"))} on logged rows</td><td>A correct abstain counts as a hit</td></tr>
        <tr><td>Human agreement</td><td>{truth.get("human_n", 0)} reviews</td><td>Plot it. Empty is not a curve.</td></tr>
        <tr><td>Calibration error</td><td>Not measured</td><td>Under 5 points across confidence bins</td></tr>
      </table>
    </div>
  </div>

  <h2>Translation and the demo lesson</h2>
  {_lang_bars(languages)}
  <p>Bars are playable files: the segment count matches the live lesson. The cache still holds older padded files, often 108 segments, and the app refuses those. The live catalog is {courses} courses. Cantonese is its own file, <code>yue.json</code>, and it is not one of the 27 platform languages. Playable Cantonese: {yue_playable}. Still partial: {yue_partial}.</p>
  <p>Demo <code>{e(translation.get("demo_course") or "audio-intro-to-machine-learning")}</code>: {demo_bits}. Intro to Machine Learning is the course to show. Until Mandarin, Khmer, and Cantonese match its real length, the visitor hears English.</p>
  <table>
    <tr><th>Language</th><th>Playable</th><th>Partial</th></tr>
    {"".join("<tr><td>" + e(row["code"]) + "</td><td>" + str(row["playable"]) + "/" + str(row["total"]) + "</td><td>" + str(row["partial"]) + "</td></tr>" for row in languages) or "<tr><td colspan=3>Translation cache was not scanned.</td></tr>"}
  </table>

  <h2>Voice agents</h2>
  <table>
    <tr><th>Path</th><th>Measured state</th><th>Needed for a lesson</th></tr>
    <tr><td>Edge neural voice</td><td>A dedicated voice for every language xAI’s speech-to-speech table cannot speak: Dutch, Polish, Ukrainian, Hebrew, Urdu, Persian, Thai, Swahili, Greek, Czech, Khmer, and Cantonese.</td><td>Lesson text in that language, at the lesson’s real length.</td></tr>
    <tr><td>xAI voice</td><td>16 languages, with a real hint. Mandarin stays on hint <code>zh</code>. An empty hint is no longer sent for the 12 above.</td><td>Do not send <code>yue</code> or Khmer into that socket.</td></tr>
    <tr><td>Khmer CosyVoice</td><td>One full 8-epoch pass, not promoted. The job is held.</td><td>A listening check before any promotion, and no restart from the base weights while the exam is on the GPU.</td></tr>
    <tr><td>Cantonese text</td><td>{yue_playable} playable course files. The demo has no <code>yue.json</code>.</td><td>Finish the demo file, then HiuMaan has Cantonese to read.</td></tr>
  </table>

  <h2>Deep specializations and tabular mastery</h2>
  <p>The product already names specialist prep: OSHA, HIPAA, food handler, CompTIA, HVAC EPA, ASE, pharmacy tech, real estate, CPR, DMV. Those ids sit in <code>CERTIFIABLE_LESSONS</code>. A specialization is reliable only when each objective has its own row: items, difficulty, pass mark, and a human-signed key. That is a table, not a chat model.</p>
  <p>There is still no fitted item-response or logistic mastery model. What we have is the subject table above, plus a frozen 200-item exam and a 96-item STEM exam. The language model explains. The table is what an auditor can recompute.</p>
  <table>
    <tr><th>Tabular field</th><th>Why it exists</th><th>Status</th></tr>
    <tr><td>Item id, objective, keyed answer</td><td>A pass mark needs a stable item</td><td>Frozen 200 and STEM 96 are the Spark scores. The 41-item split is no longer the promotion score.</td></tr>
    <tr><td>Difficulty and discrimination</td><td>Stops a lucky pass on easy items</td><td>Not fitted</td></tr>
    <tr><td>Group and subject means</td><td>Bias and dependency</td><td>Subject means are measured. One item is enough to set the floor. Frozen gap {_pct(snapshot.get("frozen_gap"))}.</td></tr>
    <tr><td>Attempt, abstain, human agree</td><td>Truth curve</td><td>Groundedness and abstention are logged. Human agreement is empty.</td></tr>
    <tr><td>Signer, body, card id</td><td>Accreditation</td><td>Card issuance is off in code</td></tr>
  </table>

  <h2>Accreditation dependencies</h2>
  <p>A completion record is withheld until the published program has at least 200 slides, it includes a summative check, and a human of record has signed it. The training floor is {TRAINING_FLOOR:.0%}. The accreditation floor is {ACCREDITATION_FLOOR:.0%}. The view returned to the app sets the external card to false. Guests can sample. A credited attempt needs a registered account, and a face, voice, and government-id check is required before the first full credited lesson. None of that issues an OSHA card, a DMV card, or a state diploma. Prep courses can teach toward those bodies. Salareen does not print their cards.</p>
  <table>
    <tr><th>Dependency</th><th>If it fails</th></tr>
    <tr><td>Registered account</td><td>Guest cannot start or be marked passed on a certifiable lesson</td></tr>
    <tr><td>Identity assurance</td><td>No first full credited lesson</td></tr>
    <tr><td>Program length ≥ 200 slides</td><td>The deck stays a sample</td></tr>
    <tr><td>Summative check</td><td>No completion record</td></tr>
    <tr><td>Human signature</td><td>Draft stays a draft</td></tr>
    <tr><td>Subject floor</td><td>A signature on a tutor whose weakest subject is {_pct(frozen_weak.get("score"))} would not be a reliable credential</td></tr>
    <tr><td>Outside body</td><td>Still no card. This software does not issue one.</td></tr>
  </table>

  <h2>Cleaning</h2>
  <table>
    <tr><th>Cleaner</th><th>What it does</th><th>What is still dirty</th></tr>
    <tr><td>Dedup</td><td>Drops near-copy documents at Jaccard 0.8</td><td>The nightly loop still retrains the same 373 examples and lands on the same frozen score</td></tr>
    <tr><td>Fairness guardrail</td><td>Training context is pedagogical. Race and ethnicity are excluded.</td><td>Subject collapse is now gated at {TRAINING_FLOOR:.0%}, and the weakest subjects fail it</td></tr>
    <tr><td>Khmer text filter</td><td>Training text must be mostly Khmer script</td><td>The demo’s stored Khmer file is the old padded lesson, so it is not served</td></tr>
    <tr><td>Translation length check</td><td>A file is served only when its segment count matches the lesson</td><td>About {max((row["playable"] for row in languages), default=0)} of {courses} courses are playable in the languages this machine is writing. The demo is not among the finished ones.</td></tr>
    <tr><td>Padding removal</td><td>The catalog no longer appends “Related context” from other topics</td><td>The cache still holds those padded files. The batch rewrites them when it reaches the course.</td></tr>
    <tr><td>Promotion gate</td><td>Keeps an adapter only when the frozen score rises and every subject clears the floor</td><td>The score is not rising. The gate is doing the refusing.</td></tr>
  </table>

  <h2>Common scores, with our number beside the target</h2>
  <table>
    <tr><th>Score</th><th>Measured</th><th>Gate we already encode</th><th>Before a specialization is called reliable</th></tr>
    <tr><td>Frozen token overlap</td><td>{_pct(frozen)} adapter, {_pct(snapshot.get("frozen_base"))} base. Served model {_pct(snapshot.get("served_accuracy"))} on {snapshot.get("served_n") or "—"} items.</td><td>Must rise, or the adapter is not kept. The served model won the bake-off and was still not promoted.</td><td>70% on this frozen set</td></tr>
    <tr><td>Split token overlap</td><td>{_pct(split)} adapter, {_pct(snapshot.get("split_base"))} base</td><td>Reported, not sufficient to promote</td><td>Not the promotion score</td></tr>
    <tr><td>STEM exam</td><td>{_pct(stem)}, weakest {e(str(stem_weak.get("subject") or "—"))} {_pct(stem_weak.get("score"))}</td><td>Required when the nightly passes stem metrics</td><td>No subject under 70%</td></tr>
    <tr><td>Fairness gap</td><td>Frozen {_pct(snapshot.get("frozen_gap"))}. Split {_pct(snapshot.get("split_gap"))}.</td><td>Bake-off still rejects a gap above 10 points</td><td>5 points, and publish the groups</td></tr>
    <tr><td>Subject floor</td><td>Weakest frozen subject {_pct(frozen_weak.get("score"))}</td><td>{TRAINING_FLOOR:.0%}, and one item counts</td><td>{ACCREDITATION_FLOOR:.0%} before a signature</td></tr>
    <tr><td>Groundedness</td><td>{_pct(truth.get("groundedness"))} on {truth.get("n", 0)} rows</td><td>Logged. Pass mark in the guard is 70% of claims.</td><td>90%, else abstain</td></tr>
    <tr><td>Human agreement</td><td>{truth.get("human_n", 0)} reviews</td><td>Field exists and is empty</td><td>A plotted curve, not a drawing</td></tr>
    <tr><td>Speech token accuracy</td><td>27.4% on the last Khmer dev pass</td><td>That pass was not promoted, and the job is held</td><td>A blind listening check before promotion</td></tr>
    <tr><td>Translation coverage</td><td>Cantonese {yue_playable}/{courses}. Demo not playable.</td><td>Length must match</td><td>222 courses in Mandarin, Cantonese, and Khmer, same shape as the lesson</td></tr>
    <tr><td>Credential issuance</td><td>0 cards</td><td>Off until a person signs and the subject floor clears</td><td>Leave it off</td></tr>
  </table>

  <h2>The path</h2>
  <div class="flow" aria-label="Path from clean data to a served lesson">
    <div class="step"><b>1 Clean</b><p>Script filter, dedup, and drop padded lessons.</p><em>Pipeline is built. The demo cache is still padded.</em></div>
    <div class="step"><b>2 Frozen exam</b><p>200 items, fixed, plus 96 STEM items.</p><em>Scored. Adapter {_pct(frozen)}. Not rising.</em></div>
    <div class="step"><b>3 Train</b><p>One GPU lock. Khmer is held.</p><em>The last cycle finished and the shell is stopped. Same 373 examples, same score.</em></div>
    <div class="step"><b>4 Fairness</b><p>Gap under 10 points, and no subject under {TRAINING_FLOOR:.0%}.</p><em>The gap passes. The subjects do not.</em></div>
    <div class="step"><b>5 Ground</b><p>Every claim overlaps the lesson, or the tutor abstains.</p><em>Logged at {_pct(truth.get("groundedness"))}. No human marks.</em></div>
    <div class="step"><b>6 Human sign</b><p>200-slide program, summative check, person of record.</p><em>Cards stay off.</em></div>
    <div class="step"><b>7 Serve</b><p>Same-shape text and a voice for Mandarin, Cantonese, and Khmer.</p><em>The demo still speaks English.</em></div>
  </div>

  <h2>Scenarios</h2>
  <div class="scene">
    <div class="card">
      <h3>Demo, Intro to Machine Learning</h3>
      <p>A visitor taps Start. The lesson is its own short English deck. Mandarin and Khmer files on disk are the old 108-segment copies, so the app will not play them. Cantonese has no file for this course. This remains the demo. It is not ready to demonstrate three languages.</p>
    </div>
    <div class="card">
      <h3>Khmer parent, audio on the drive</h3>
      <p>They pick Khmer. Sreymom can speak Khmer. The stored demo file is the wrong shape, so the lesson falls back to English. The fine-tune is not what they will hear, and it is not running.</p>
    </div>
    <div class="card">
      <h3>Cantonese learner</h3>
      <p>Cantonese is <code>yue</code>, written to its own file, with HiuMaan as the voice. {yue_playable} courses are playable. This demo is not one of them. Sending the lesson to Grok as Mandarin would be the wrong language, and the voice plan does not do that.</p>
    </div>
    <div class="card">
      <h3>Accredited OSHA pass</h3>
      <p>The id is listed. A guest is stopped. A registered learner still cannot receive an outside card. Signing that program on top of a frozen score of {_pct(frozen)}, with Health &amp; Wellness at {_pct(frozen_weak.get("score"))}, would put a name on a tutor that has not cleared the floor.</p>
    </div>
  </div>

  <h2>Where to go next, in order</h2>
  <ol>
    <li>Stop spending cycles on the same 373 examples. The frozen score stays {_pct(frozen)} until the training data or the objective changes. Keep an adapter only when that number rises and every subject is at least {TRAINING_FLOOR:.0%}.</li>
    <li>Add items for the subjects that set the floor. Health &amp; Wellness is {_pct(frozen_weak.get("score"))} on the frozen exam. Calculus 1 is {_pct(stem_weak.get("score"))} on the STEM exam. Python files is {_pct(weak.get("score"))} on the split. Linear algebra is {_pct(algebra)} on its 4-item STEM exam and still under 40% on the split.</li>
    <li>Have a person mark truth-log rows. Groundedness is {_pct(truth.get("groundedness"))} and abstention is {_pct(truth.get("abstain_accuracy"))}. Human agreement is blank, so the teal diagonal is still a target.</li>
    <li>Resume the 222-course batch. It is stopped at {done} of {total}, with {failed} failures after the gateway went down. Bring the CPU translator back, then let the run finish. Cantonese is playable for {yue_playable} courses. Rewrite Intro to Machine Learning so Mandarin, Khmer, and Cantonese match the lesson. Until then the demo speaks English.</li>
    <li>Keep Khmer CosyVoice off this GPU. The next voice run, when the exam is finished, starts from the last real checkpoint after a listening check. It does not start from the base weights.</li>
    <li>Leave outside cards off until a person of record signs a program whose weakest subject clears {ACCREDITATION_FLOOR:.0%}.</li>
  </ol>
  <p>Already in place, so they are not the next move: the frozen 200 is the Spark score, a repeated promotion is refused, one weak item sets a {TRAINING_FLOOR:.0%} floor, groundedness and abstention are logged, Cantonese is its own translation file, languages xAI cannot speak use our neural voices, and the card flag stays false.</p>

  <h2>History</h2>
  <table>
    <tr><th>When</th><th>Frozen</th><th>Weakest split</th><th>Groundedness</th><th>Cantonese playable</th><th>Gate</th></tr>
    {"".join(hist_rows) or "<tr><td colspan=6>No history yet. This snapshot is the baseline.</td></tr>"}
  </table>
</main>
<footer>
  <p>Sources: frozen exam <code>stem.frozen.json</code>, STEM exam <code>stem.stemfrozen.json</code>, split <code>stem.json</code>, truth log, translation cache, and the 222-course batch log. Historical charts end 22 Oct 2026, 5 AM PT. Rebuild with <code>python3 training/frontier_readiness.py --record</code>. Snapshot {e(snapshot["at"])}.</p>
</footer>
</body>
</html>
"""
