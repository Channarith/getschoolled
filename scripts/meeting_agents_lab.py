#!/usr/bin/env python3
"""Offline lab: harvest → teach → bridge → multi-agent video class.

Exercises Google Meet, Zoom, and Teams paths with simulated media/chat — no
vendor SDKs, keys, or network required. Validates:

  Part 1  Harvester pipeline (scored course)
  Part 2  AI presenter script (with regional dialect)
  Part 3  Bridge connect + chat read/reply bots
  Agents  Teacher, chat tutor, perception, interrupt host, moderator,
          adaptive coach, critical-thinking coach, situational analyst,
          rapid-response coach, forecasting mentor, emergency-sim coach

Usage:
  python3 scripts/meeting_agents_lab.py --platform zoom --dialect us_ca
  python3 scripts/meeting_agents_lab.py --platform teams --dialect us_tx
  python3 scripts/meeting_agents_lab.py --platform meet --dialect es_mx --all
  python3 scripts/meeting_agents_lab.py --scenario aviation_emergency_engine_loss
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.dialect import list_dialects  # noqa: E402
from aoep_shared.meeting_agents import run_meeting_agents_lab  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Offline meeting agents lab")
    p.add_argument("--platform", choices=["zoom", "teams", "meet"], default="zoom")
    p.add_argument("--dialect", default="us_ca",
                   help="Regional tone: us_ca, us_tx, us_general, es_mx, pt_br, ...")
    p.add_argument("--language", default="en")
    p.add_argument("--subject", default="chemistry")
    p.add_argument("--scenario", default="aviation_emergency_engine_loss")
    p.add_argument("--scenario-risk", type=float, default=0.62)
    p.add_argument("--out", type=Path, default=None, help="Keep artifacts here")
    p.add_argument("--all", action="store_true", help="Run zoom + teams + meet")
    p.add_argument("--list-dialects", action="store_true")
    args = p.parse_args()

    if args.list_dialects:
        for d in list_dialects():
            print(f"{d['id']:12} {d['label']:20} ({d['language']})")
        return 0

    platforms = ["zoom", "teams", "meet"] if args.all else [args.platform]
    failed = 0
    for plat in platforms:
        print(f"\n=== {plat.upper()} · dialect={args.dialect} ===")
        result = run_meeting_agents_lab(
            platform=plat,
            dialect=args.dialect,
            language=args.language,
            subject=args.subject,
            scenario=args.scenario,
            scenario_risk=args.scenario_risk,
            out_dir=args.out,
        )
        for label, ok in result.checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        passed = sum(1 for _, ok in result.checks if ok)
        total = len(result.checks)
        print(f"{passed}/{total} checks · {len(result.agent_events)} agent events")
        print(f"Chat outbound: {len(result.chat_sent)} messages")
        if result.artifacts.get("lab_report"):
            print(f"Report: {result.artifacts['lab_report']}")
        if passed != total:
            failed += 1

    if failed:
        print(f"\n{failed} platform run(s) failed.", file=sys.stderr)
        return 1
    print("\nMEETING AGENTS LAB OK — safe to integrate into the ecosystem.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
