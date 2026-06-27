"""Tests for scenario-based training agents."""

import pytest

from aoep_shared.training_agents import (
    TrainingSession,
    agent_roster_dict,
    all_facts,
    catalog_capacity,
    catalog_meta,
    count_scenarios,
    count_scenarios_for_track,
    facts_for,
    generate_scenario,
    get_scenario,
    get_track,
    knowledge_overview,
    knowledge_source_list,
    list_domains,
    list_families_meta,
    list_scenarios,
    list_scenarios_for_track,
    list_tracks,
    random_procedural_scenario,
    random_scenario,
    reload_catalog,
    search_knowledge,
)


def test_knowledge_base_is_real_and_cited():
    facts = all_facts()
    assert len(facts) >= 60
    for f in facts:
        assert f.fact and f.source and f.reference
    meta = knowledge_overview()
    assert meta["sources"] >= 30
    # Real authorities must be represented.
    sources = {s["source"] for s in knowledge_source_list()}
    assert any("NHTSA" in s for s in sources)
    assert any("FAA" in s for s in sources)
    assert any("USCG" in s for s in sources)
    assert any("Heart Association" in s for s in sources)


def test_knowledge_search_by_domain_and_query():
    total, items = search_knowledge(domain="marine", limit=50)
    assert total >= 3
    assert all(items)
    _, cpr = search_knowledge(q="compressions", limit=10)
    assert any("100" in f["fact"] for f in cpr)


def test_scenarios_are_grounded_in_real_data():
    s = get_scenario("road_car__1000")
    assert s is not None
    assert s.references
    assert all(r.source and r.reference for r in s.references)
    # CPR fact should ground a cardiac medical scenario.
    facts = facts_for("medical", text="cardiac arrest unresponsive compressions")
    assert any("compressions" in f.fact.lower() for f in facts)


def test_generated_scenario_carries_references():
    s = generate_scenario("boat", 500)
    assert s is not None
    assert s.references
    assert any("USCG" in r.source or "COLREGs" in r.reference or "IMO" in r.source
               for r in s.references)


def test_capacity_reaches_millions():
    cap = catalog_capacity()
    assert cap["procedural_capacity"] >= 1_000_000
    assert cap["total_addressable"] >= 1_000_000
    assert len(cap["families"]) >= 12


def test_transport_and_safety_domains_present():
    domains = {d for d, _ in list_domains()}
    for dom in ("road", "rail", "micromobility", "marine", "pedestrian", "police", "school_safety"):
        assert dom in domains


def test_families_cover_requested_modes():
    fam_ids = {f["family_id"] for f in list_families_meta()}
    for fid in (
        "road_car", "road_motorcycle", "road_truck", "road_bus",
        "rail_train", "rail_transit", "bicycle", "scooter",
        "boat", "watercraft", "pedestrian", "police",
        "school_student", "school_teacher",
    ):
        assert fid in fam_ids


def test_generate_scenario_is_deterministic():
    a = generate_scenario("road_car", 12345)
    b = generate_scenario("road_car", 12345)
    assert a is not None and b is not None
    assert a.scenario_id == b.scenario_id == "road_car__12345"
    assert a.briefing == b.briefing
    diff = generate_scenario("road_car", 12346)
    assert diff.briefing != a.briefing


def test_get_scenario_resolves_procedural_id():
    s = get_scenario("bicycle__999")
    assert s is not None
    assert s.domain.value == "micromobility"


def test_run_procedural_scenario_in_session():
    session = TrainingSession.start("police__500")
    seen = set()
    for _ in range(14):
        for t in session.tick():
            seen.add(t.agent)
        if session.state.phase.value == "done":
            break
    assert session.state.cues_seen
    assert "situational_analysis" in seen


def test_catalog_has_thousands_materialized():
    meta = catalog_meta()
    assert meta["count"] >= 3000
    assert count_scenarios() >= 3000
    assert len(list_domains()) >= 40


def test_extended_domains_present():
    domains = {d for d, _ in list_domains()}
    for dom in ("nursing", "hazmat", "aviation_ifr", "wilderness", "pharma"):
        assert dom in domains


def test_training_tracks_exist_and_have_scenarios():
    tracks = list_tracks()
    assert len(tracks) >= 20
    pilot = get_track("pilot_emergency")
    assert pilot is not None
    assert count_scenarios_for_track("pilot_emergency") >= 20
    road = get_track("road_safety")
    assert road is not None
    assert count_scenarios_for_track("road_safety") >= 100


def test_random_scenario_deterministic_with_seed():
    a = random_scenario(track_id="first_responder", seed=42)
    b = random_scenario(track_id="first_responder", seed=42)
    assert a is not None and b is not None
    assert a.scenario_id == b.scenario_id


def test_random_procedural_deterministic_with_seed():
    a = random_procedural_scenario(family_id="road_car", seed=7)
    b = random_procedural_scenario(family_id="road_car", seed=7)
    assert a is not None and b is not None
    assert a.scenario_id == b.scenario_id


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
    road = list_scenarios(domain="road", limit=100)
    assert road
    assert all(s.domain.value == "road" for s in road)


def test_list_scenarios_search():
    hits = list_scenarios(q="brake", limit=20)
    assert hits


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
    assert count_scenarios() >= 3000
