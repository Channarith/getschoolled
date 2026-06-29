"""Consolidation: cognitive stack unified under training_agents."""

from aoep_shared import training_agents
from aoep_shared.training_agents import (
    CognitiveTrainer,
    agent_roster_dict,
    get_scenario,
    list_agents,
    scenarios_from_cognitive,
)


def test_cognitive_engines_importable_from_training_agents():
    # Single canonical home: the cognitive facade is re-exported.
    assert hasattr(training_agents, "CognitiveTrainer")
    assert hasattr(training_agents, "CognitiveLearnerProfile")
    assert hasattr(training_agents, "LearningPattern")
    trainer = CognitiveTrainer()
    profile = trainer.create_profile("learner-1")
    assert profile.learner_id == "learner-1"


def test_roster_includes_cognitive_agents():
    roles = {a["role_id"] for a in agent_roster_dict()}
    for rid in (
        "cognitive_coach", "critical_thinking_trainer", "situational_awareness_trainer",
        "rapid_decision_trainer", "emergency_scenario_trainer", "mental_readiness_trainer",
    ):
        assert rid in roles
    cognitive = list_agents(category="cognitive")
    assert len(cognitive) == 6


def test_cognitive_scenarios_promoted_to_catalog():
    promoted = scenarios_from_cognitive()
    assert len(promoted) >= 13
    ids = {s.scenario_id for s in promoted}
    assert "em_av_engine_failure" in ids
    assert "sa_med_01" in ids
    assert "rd_cyber_01" in ids
    # Domains correctly mapped to canonical catalog domains.
    by_id = {s.scenario_id: s for s in promoted}
    assert by_id["em_crisis_ransomware"].domain.value == "security"
    assert by_id["sa_fire_01"].domain.value == "fire_safety"


def test_promoted_scenarios_resolvable_via_catalog():
    # Committed cognitive_gold pack means the unified catalog can serve them.
    s = get_scenario("em_av_engine_failure")
    assert s is not None
    assert s.briefing
    assert s.emergency_steps  # built from the branching phase tree experts
