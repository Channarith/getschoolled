"""Tests for scenario-based training agents."""

import pytest

from aoep_shared.training_agents import (
    TrainingSession,
    agent_roster_dict,
    get_scenario,
    list_scenarios,
)


def test_builtin_scenarios_include_aviation_emergency():
    scenarios = list_scenarios()
    ids = {s.scenario_id for s in scenarios}
    assert "aviation_emergency_landing" in ids
    av = get_scenario("aviation_emergency_landing")
    assert av is not None
    assert len(av.emergency_steps) >= 4
    assert any("Aviate" in s for s in av.emergency_steps)


def test_agent_roster_includes_harvester_presenter_chatbot_and_coaches():
    roster = agent_roster_dict()
    role_ids = {a["role_id"] for a in roster}
    for rid in (
        "harvester", "presenter", "chatbot",
        "learning_coach", "critical_thinking", "situational_analysis",
        "quick_decision", "foresight_prep", "emergency_training",
    ):
        assert rid in role_ids


def test_training_session_tick_progresses_phases():
    session = TrainingSession.start("fire_evacuation")
    agents_seen = set()
    for _ in range(12):
        turns = session.tick()
        for t in turns:
            agents_seen.add(t.agent)
        if session.state.phase.value == "done":
            break
    assert "situational_analysis" in agents_seen
    assert session.state.cues_seen


def test_training_session_respond_records_learner():
    session = TrainingSession.start("media_claim_verification")
    for _ in range(4):
        session.tick()
    turns = session.respond("I would not share because there is no clinical evidence.")
    assert session.state.learner_responses
    assert turns
    assert any(
        t.agent in (
            "critical_thinking", "learning_coach", "quick_decision", "situational_analysis",
        )
        for t in turns
    )


def test_aviation_emergency_coach_and_debrief():
    session = TrainingSession.start("aviation_emergency_landing")
    for _ in range(20):
        session.tick()
    session.respond("Aviate first — maintain glide, then navigate to the airport.")
    for _ in range(15):
        turns = session.tick()
        if session.state.phase.value == "done":
            break
    assert session.state.score is not None or any(
        t.kind == "debrief" for t in turns
    )


def test_unknown_scenario_raises():
    with pytest.raises(ValueError, match="unknown scenario"):
        TrainingSession.start("not_a_real_scenario")
