"""Consolidation bridge: unify the cognitive_trainer engines under training_agents.

PR #200 added a parallel, pedagogically rich cognitive stack as flat modules
(``aoep_shared.cognitive_trainer`` + critical_thinking / situational_awareness /
rapid_decision / emergency_scenarios / mental_readiness) served at
``/api/cognitive/*``. This module makes ``training_agents`` the single canonical
home for all training/cognitive capability:

1. Re-exports the cognitive engines so callers import them from one place.
2. Promotes the cognitive stack's curated, high-fidelity built-in scenarios and
   drills into Implementation A's scenario catalog (as ScenarioDefinition records)
   so there is ONE browsable catalog (``/api/training/scenarios``) instead of two.

The cognitive engines remain the source of truth for their interactive logic
(Bloom scoring, OODA/DECIDE, branching sims + AAR); this bridge just unifies the
discovery/catalog surface. Pure/stdlib + numpy-free.
"""

from __future__ import annotations

from typing import List

# Re-export the cognitive engines from their canonical home.
from aoep_shared.cognitive_trainer import (  # noqa: F401
    BehaviorAdaptationAgent,
    CognitiveLearnerProfile,
    CognitiveTrainer,
    LearningPattern,
)
from aoep_shared.emergency_scenarios import list_emergency_scenarios
from aoep_shared.rapid_decision import list_drills
from aoep_shared.situational_awareness import list_scenarios as list_sa_scenarios

from .models import ScenarioCue, ScenarioDefinition, ScenarioDomain

# Map the cognitive stack's domain vocabulary to canonical catalog domains.
_DOMAIN_MAP = {
    "aviation": "aviation",
    "medical": "medical",
    "fire": "fire_safety",
    "fire_evacuation": "fire_safety",
    "crisis": "security",
    "industrial": "industrial",
    "cyber": "cybersecurity",
    "cyber_security": "cybersecurity",
    "triage": "medical",
    "finance": "finance",
}


def _domain(value: str) -> ScenarioDomain:
    raw = (value or "general").lower()
    return ScenarioDomain.from_value(_DOMAIN_MAP.get(raw, raw))


def _emergency_to_scenarios() -> List[ScenarioDefinition]:
    out: List[ScenarioDefinition] = []
    for e in list_emergency_scenarios():
        phases = [e.phases[pid] for pid in e.phases]
        initial = e.phases.get(e.initial_phase_id)
        cues = [
            ScenarioCue(cue_id=p.phase_id, text=p.situation_update[:160],
                        priority="high" if i == 0 else "medium")
            for i, p in enumerate(phases)
        ]
        steps = []
        for p in phases:
            expert = next((a for a in p.available_actions if a.action_id == p.expert_action_id),
                          None)
            label = expert.label if expert else p.title
            tp = f" — {p.teaching_point}" if p.teaching_point else ""
            steps.append(f"{p.title}: {label}{tp}")
        out.append(ScenarioDefinition(
            scenario_id=e.scenario_id,
            title=e.title,
            domain=_domain(e.domain.value),
            briefing=e.description,
            cues=cues,
            decision_prompt=(initial.action_prompt if initial else
                             "State your first action sequence and priorities."),
            decision_time_limit_s=(initial.time_window_seconds or 60) if initial else 60,
            emergency_steps=steps,
            foresight_prompts=list(e.learning_objectives[:3]),
            critical_thinking_prompts=[
                f"Why is the expert action best at: {p.title}?" for p in phases[:3]
            ],
            debrief_rubric=list(e.learning_objectives),
            skills=list(e.prerequisite_skills) + ["emergency-procedures", "branching-simulation"],
        ))
    return out


def _sa_to_scenarios() -> List[ScenarioDefinition]:
    out: List[ScenarioDefinition] = []
    for s in list_sa_scenarios():
        cues = [
            ScenarioCue(cue_id=c.cue_id, text=c.description,
                        priority="critical" if c.critical else "medium")
            for c in s.cues
        ]
        out.append(ScenarioDefinition(
            scenario_id=s.scenario_id,
            title=s.title,
            domain=_domain(s.domain),
            briefing=s.description,
            cues=cues,
            decision_prompt="Scan the situation (OODA/DECIDE): what is the correct decision and why?",
            decision_time_limit_s=s.time_pressure_seconds or 60,
            foresight_prompts=["What cue would warn you earliest?"],
            critical_thinking_prompts=list(s.common_mistakes[:3]),
            debrief_rubric=[s.correct_decision] + list(s.common_mistakes[:3]),
            skills=["situational-analysis", "ooda-decide", _domain(s.domain).value],
        ))
    return out


def _rapid_to_scenarios() -> List[ScenarioDefinition]:
    out: List[ScenarioDefinition] = []
    for d in list_drills():
        options = "; ".join(f"{o.label}) {o.text}" for o in d.options)
        out.append(ScenarioDefinition(
            scenario_id=d.drill_id,
            title=f"Rapid drill: {d.situation[:60]}",
            domain=_domain(d.domain),
            briefing=d.situation,
            cues=[ScenarioCue(cue_id="key_cue", text=d.cue_to_spot, priority="high")],
            decision_prompt=f"Decide fast — choose the best option: {options}",
            decision_time_limit_s=max(5, int(round(d.ideal_seconds * 2))),
            foresight_prompts=[f"What is the recognition cue that short-circuits deliberation?"],
            critical_thinking_prompts=[f"Common failure mode under pressure: {d.failure_mode}"],
            debrief_rubric=[
                f"Spot the cue: {d.cue_to_spot}",
                f"Avoid the failure mode: {d.failure_mode}",
            ],
            skills=[d.skill_tag, "quick-decision", _domain(d.domain).value],
        ))
    return out


def scenarios_from_cognitive() -> List[ScenarioDefinition]:
    """All curated cognitive-stack scenarios/drills as catalog ScenarioDefinitions."""
    return _emergency_to_scenarios() + _sa_to_scenarios() + _rapid_to_scenarios()


def cognitive_scenario_records() -> List[dict]:
    """Serializable scenario records for a content pack (kind=scenarios)."""
    from .catalog_builder import scenario_to_dict

    return [scenario_to_dict(s) for s in scenarios_from_cognitive()]
