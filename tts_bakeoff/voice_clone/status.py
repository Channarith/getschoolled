"""`bakeoff status --out RUN`: read-only. What is done per voice and language, what is running now, an ETA, and one final line.

Final line: RUNNING (a worker is alive), DONE (every planned clip exists and nothing runs) or INCOMPLETE (nothing runs, clips missing).
The plan comes from the run's own progress.json; --speakers/--models/--langs describe a plan instead when there is none yet.
"""
from __future__ import annotations

import json
from pathlib import Path

from tts_bakeoff.build_sentences import load

from . import progress, registry, runner

MAX_TODO = 14


def _expected(a, out: Path) -> list[dict] | None:
    explicit = bool(a.speakers or a.models or a.langs)
    summary_path = out / progress.SUMMARY
    if not explicit and summary_path.is_file():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8")).get("units")
        except (OSError, ValueError):
            return None
    if not explicit:
        return None
    speakers = [s for s in a.speakers.split(",") if s] or registry.list_speakers()
    models = [m for m in a.models.split(",") if m] or ["voxcpm2", "cosyvoice2"]
    langs = runner.SUPPORTED if a.langs == "all" else ([x for x in a.langs.split(",") if x] or None)
    plan = runner.make_plan(speakers, models, langs, quiet=True)
    return [{"speaker": u.speaker, "model": u.model, "lang": u.lang, "total": len(load(u.lang, a.limit))} for u in plan.units]


def _done_counts(out: Path) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for root in sorted(p for p in out.iterdir() if p.is_dir() and "~" in p.name and not p.name.startswith(("_", "."))):
        for row in runner.manifest_rows(root).values():
            if runner.clip_done(out, row):
                key = (root.name, row.get("lang", ""))
                counts[key] = counts.get(key, 0) + 1
    return counts


def report(a) -> tuple[list[str], str]:
    out = Path(a.out)
    done = _done_counts(out)
    units = _expected(a, out)
    lines = [f"Run folder: {out}"]
    workers = progress.read_workers(out)
    live = [w for w in workers if not w.get("finished") and progress.pid_alive(w.get("pid"))]
    total_done = total_all = 0
    if units is None:
        lines.append("No plan recorded (no progress.json yet): showing what exists. Pass --langs/--models to say what was asked for.")
        by_voice: dict[str, dict[str, int]] = {}
        for (vid, lang), n in done.items():
            by_voice.setdefault(vid, {})[lang] = n
        for vid, langs in sorted(by_voice.items()):
            lines.append(f"{vid:<28} {sum(langs.values()):>4} clips in {len(langs)} language(s): " + " ".join(f"{l}:{n}" for l, n in sorted(langs.items())))
        missing = 0
        total_done = sum(done.values())
    else:
        per_voice: dict[str, list[tuple[str, int, int]]] = {}
        for u in units:
            vid = f"{u['model']}~{u['speaker']}"
            n = min(done.get((vid, u["lang"]), 0), u["total"])
            per_voice.setdefault(vid, []).append((u["lang"], n, u["total"]))
        for vid, rows in sorted(per_voice.items()):
            d, t = sum(r[1] for r in rows), sum(r[2] for r in rows)
            total_done, total_all = total_done + d, total_all + t
            complete = sum(1 for r in rows if r[1] >= r[2])
            lines.append(f"{vid:<28} {d:>4}/{t:<4} {progress.bar(d, t)}   languages complete {complete}/{len(rows)}")
            todo = [f"{l} {n}/{t2}" for l, n, t2 in rows if n < t2]
            if todo:
                shown = ", ".join(todo[:MAX_TODO]) + (f"  (+{len(todo) - MAX_TODO} more)" if len(todo) > MAX_TODO else "")
                lines.append(f"{'':<28} to do: {shown}")
        missing = total_all - total_done
        lines.append(f"{'TOTAL':<28} {total_done:>4}/{total_all:<4} {progress.bar(total_done, total_all)}")
    for w in workers:
        cur = w.get("current")
        state = "finished" if w.get("finished") else ("running" if progress.pid_alive(w.get("pid")) else "NOT RUNNING (stopped or died)")
        where = f"{cur['speaker']} / {cur['model']} / {cur['lang']}" if cur else "-"
        lines.append(f"worker {w.get('worker')}: {state}  now: {where}  this run: {w.get('done', 0)} made, {w.get('skipped_existing', 0)} skipped, {w.get('failed', 0)} failed")
    if units is not None and live:
        lines.append(f"ETA: {progress.human(progress.eta_seconds(missing, workers))}  (from the last clips' times, {len(live)} worker(s))")
    holder = progress.lock_holder()
    lines.append(f"GPU lock: {holder or 'free'}")
    if live:
        verdict = "RUNNING"
    elif units is not None and missing > 0:
        verdict = f"INCOMPLETE ({missing} clip(s) missing, nothing is running)"
    else:
        verdict = "DONE"
    lines.append(verdict)
    return lines, verdict


def main(a) -> int:
    out = Path(a.out)
    if not out.is_dir():
        print(f"no such run folder: {out}")
        return 2
    lines, _verdict = report(a)
    print("\n".join(lines))
    return 0
