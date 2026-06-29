#!/usr/bin/env python3
"""Promote the cognitive stack's curated scenarios into the unified catalog.

Writes a scenarios content pack from the cognitive_trainer engines (emergency
sims, situational-awareness scenarios, rapid-decision drills) so they show up in
the single /api/training/scenarios catalog alongside the procedural library.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aoep_shared.training_agents.cognitive import cognitive_scenario_records


def main() -> int:
    out = Path(__file__).resolve().parents[1] / (
        "packages/shared/src/aoep_shared/data/content_packs/scenarios/cognitive_gold_v1.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    records = cognitive_scenario_records()
    out.write_text(json.dumps({
        "pack": "cognitive_gold_v1",
        "description": "Curated high-fidelity scenarios promoted from the cognitive trainer stack.",
        "records": records,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} cognitive scenarios -> {out}")
    for r in records:
        print(f"  {r['scenario_id']:<28} [{r['domain']}] {r['title'][:50]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
