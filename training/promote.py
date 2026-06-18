#!/usr/bin/env python3
"""Phase 19 - run the Track A vs Track B bake-off and promote the champion.

Scores both tracks' candidates on the same eval (fairness-gated), promotes the
winner into the served champion pointer (training/champion.py), and emits the
serving wiring the app should adopt (LLM_MODEL for a from-scratch champion, or
LLM_ROUTES for the Track B multi-adapter champion). Reverting = repoint the
champion to the prior entry (ChampionRegistry.revert). Offline-testable with
mock candidate metrics; the real candidates come from training/evaluate.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional, Sequence

from bakeoff import Candidate, promote_champion, run_bakeoff


def run_promotion(
    candidates: Sequence[Dict],
    *,
    champion_path: Optional[str] = None,
    primary: str = "accuracy",
    max_fairness_gap: Optional[float] = 0.1,
) -> Dict:
    """candidates: [{name, track[A|B], metrics:{accuracy, fairness_gap, ...}}]."""
    track_by_name = {c["name"]: c.get("track") for c in candidates}
    cands = [Candidate(c["name"], c.get("metrics", {})) for c in candidates]
    result = run_bakeoff(cands, primary=primary, max_fairness_gap=max_fairness_gap)

    champ = result.get("champion")
    result["track"] = track_by_name.get(champ)
    # Serving wiring suggestion.
    if champ:
        if result["track"] == "B":
            result["serving"] = {"LLM_ROUTES": "<run: python3 training/base/routes.py>"}
        else:
            result["serving"] = {"LLM_MODEL": champ}
    if champion_path and champ:
        result.update(promote_champion(result, champion_path))
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", required=True,
                    help='JSON: [{"name":...,"track":"A|B","metrics":{...}}]')
    ap.add_argument("--champion-path", default=None)
    ap.add_argument("--primary", default="accuracy")
    ap.add_argument("--max-fairness-gap", type=float, default=0.1)
    args = ap.parse_args(argv)
    data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    result = run_promotion(data, champion_path=args.champion_path,
                           primary=args.primary, max_fairness_gap=args.max_fairness_gap)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
