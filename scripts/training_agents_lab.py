#!/usr/bin/env python3
"""Offline lab for scenario training agents (critical thinking, emergency drills)."""

from __future__ import annotations

import argparse
import json
import sys

from aoep_shared.training_agents import (
    TrainingSession,
    agent_roster_dict,
    catalog_meta,
    list_scenarios,
    list_tracks,
    track_to_dict,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a training agents lab offline")
    parser.add_argument(
        "--scenario", default="aviation_emergency_landing",
        help="Scenario id (default: aviation_emergency_landing)",
    )
    parser.add_argument("--ticks", type=int, default=10, help="Number of ticks")
    parser.add_argument("--respond", default="", help="Optional learner response after ticks")
    parser.add_argument("--list", action="store_true", help="List scenarios and roster")
    args = parser.parse_args()

    if args.list:
        meta = catalog_meta()
        print(f"Catalog: {meta['count']} scenarios across {len(meta['domains'])} domains")
        for domain, n in sorted(meta["domains"].items(), key=lambda x: -x[1])[:12]:
            print(f"  {domain}: {n}")
        print("  ...")
        print("\nLearning tracks:")
        for t in list_tracks():
            print(f"  {t.track_id}: {t.title}")
        print("\nSample scenarios:")
        for s in list_scenarios(limit=8):
            print(f"  {s.scenario_id}: {s.title} [{s.domain.value}]")
        print("\nAgent roster:")
        for a in agent_roster_dict():
            print(f"  {a['role_id']}: {a['name']} ({a['category']})")
        return 0

    session = TrainingSession.start(args.scenario)
    report = {"scenario": args.scenario, "session_id": session.session_id, "turns": []}

    for _ in range(args.ticks):
        for turn in session.tick():
            report["turns"].append({
                "agent": turn.agent, "kind": turn.kind, "message": turn.message,
            })

    if args.respond:
        for turn in session.respond(args.respond):
            report["turns"].append({
                "agent": turn.agent, "kind": turn.kind, "message": turn.message,
            })

    report["final"] = session.to_view()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
