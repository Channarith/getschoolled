"""Offline lab: run a full critical-thinking / emergency drill end-to-end.

Drives the flagship engine-out scenario through every cognitive agent with a
scripted learner (a deliberate mix of sharp and sloppy decisions) so the whole
pipeline - situational awareness, forecasting, rapid decision, critical
thinking, and behavior adaptation - is exercised without a model server.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from aoep_shared.schemas import ClassType

from .engine import TrainingSession
from .scenario import get_scenario

# (option_id, elapsed_s, rationale) for the flagship engine-out scenario. Mixes a
# crisp correct opener, a slow emotional wrong call, a panicked fixation, then a
# clean recovery - so behavior adaptation and the bias detector both fire.
_DEFAULT_SCRIPT: List[Tuple[str, float, str]] = [
    ("pitch_best_glide", 5.0,
     "Nose is high and airspeed is bleeding, so I lower the nose for best glide first because Aviate comes before anything else."),
    ("highway", 16.0, "I just feel like the road is safer, I guess."),
    ("obsess_restart", 15.0, "Panic - I keep trying the starter."),
    ("mayday_squawk", 6.0,
     "Quick mayday on 121.5 and squawk 7700 because help should be moving while I keep flying the approach."),
    ("secure_brace", 7.0,
     "Fuel off, mags and master off, doors unlatched because cutting fuel and sparks reduces post-impact fire risk, then touch down slow."),
]


@dataclass
class TrainingAgentsLabResult:
    scenario_id: str
    decisions: List[dict]
    agent_events: List[dict]
    summary: dict
    checks: List[Tuple[str, bool]] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "decisions": self.decisions,
            "agent_events": self.agent_events,
            "summary": self.summary,
            "checks": [{"label": a, "ok": b} for a, b in self.checks],
            "artifacts": self.artifacts,
        }


def _check(results: List[Tuple[str, bool]], label: str, ok: bool) -> None:
    results.append((label, bool(ok)))


def run_training_agents_lab(
    *,
    scenario_id: str = "engine-out-emergency-landing",
    class_type: ClassType = ClassType.SOLO,
    script: Optional[List[Tuple[str, float, str]]] = None,
    out_dir: Optional[str | Path] = None,
) -> TrainingAgentsLabResult:
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise ValueError(f"unknown scenario {scenario_id!r}")
    script = script or _DEFAULT_SCRIPT

    session = TrainingSession(scenario=scenario, class_type=class_type)
    checks: List[Tuple[str, bool]] = []
    decisions: List[dict] = []
    events: List[dict] = []

    for option_id, elapsed_s, rationale in script:
        if session.done:
            break
        brief = session.brief()
        events.append({
            "agent": "situational_awareness", "phase": brief.phase_id,
            "detail": brief.situation_picture.comprehension[0] if brief.situation_picture.comprehension else "",
            "meta": {"projection": brief.situation_picture.projection},
        })
        events.append({
            "agent": "forecasting", "phase": brief.phase_id,
            "detail": brief.premortem.headline,
            "meta": {"contingency": brief.premortem.contingency},
        })
        outcome = session.decide(option_id, elapsed_s=elapsed_s, rationale=rationale)
        decisions.append(outcome.as_dict())
        events.append({
            "agent": "rapid_decision", "phase": outcome.phase_id,
            "detail": outcome.rapid.note, "meta": outcome.rapid.ooda,
        })
        events.append({
            "agent": "critical_thinking", "phase": outcome.phase_id,
            "detail": outcome.reasoning.socratic_probe,
            "meta": {"issues": outcome.reasoning.detected_issues,
                     "score": outcome.reasoning.reasoning_score},
        })
        events.append({
            "agent": "learning_behavior", "phase": outcome.phase_id,
            "detail": outcome.behavior.recommendation,
            "meta": {"flags": outcome.behavior.flags, "tone": outcome.behavior.tone},
        })

    summary = session.summary()

    _check(checks, "Scenario completed", session.done)
    _check(checks, "All five agents acted",
           {e["agent"] for e in events} >= {
               "situational_awareness", "forecasting", "rapid_decision",
               "critical_thinking", "learning_behavior"})
    _check(checks, "Pre-mortem produced for first phase",
           bool(events and events[0].get("phase")))
    _check(checks, "Bias/emotional reasoning detected",
           any(e["agent"] == "critical_thinking" and e["meta"]["issues"] for e in events))
    _check(checks, "Behavior adapted (supportive/scaffold) under load",
           any(e["agent"] == "learning_behavior" and
               (e["meta"]["flags"] or e["meta"]["tone"] != "neutral") for e in events))
    _check(checks, "Summary has per-skill scores", bool(summary["per_skill"]))
    _check(checks, "Strong opener scored high",
           bool(decisions) and decisions[0]["score"] >= 0.7)

    result = TrainingAgentsLabResult(
        scenario_id=scenario_id,
        decisions=decisions,
        agent_events=events,
        summary=summary,
        checks=checks,
    )

    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        report = out / "training_agents_lab.json"
        report.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        result.artifacts["lab_report"] = str(report)

    return result
