"""Tests for scenario-based training agents."""

import pytest

from aoep_shared.training_agents import (
    TrainingSession,
    agent_roster_dict,
    catalog_meta,
    count_scenarios,
    get_scenario,
    list_domains,
    list_scenarios,
    reload_catalog,
)


def test_catalog_has_hundreds_of_scenarios():
    meta = catalog_meta()
    assert meta["count"] >= 400
    assert count_scenarios() >= 400
    assert len(list_domains()) >= 15


def test_builtin_scenarios_include_aviation_emergency():
    av = get_scenario("aviation_emergency_landing")
    assert av is not None
    assert len(av.emergency_steps) >= 4
    assert any("Aviate" in s for s in av.emergency_steps)


def test_list_scenarios_pagination():
    page1 = list_scenarios(limit=25, offset=0)
    page2 = list_scenarios(limit=25, offset=25)
    assert len(page1) == 25
    assert page1[0].scenario_id != page2[0].scenario_id


def test_list_scenarios_domain_filter():
    aviation = list_scenarios(domain="aviation", limit=100)
    assert aviation
    assert all(s.domain.value == "aviation" for s in aviation)


def test_list_scenarios_search():
    hits = list_scenarios(q="engine", limit=20)
    assert hits
    assert any("engine" in s.title.lower() or "engine" in s.briefing.lower() for s in hits)


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


def test_reload_catalog_after_rebuild():
    reload_catalog()
    assert count_scenarios() >= 400
