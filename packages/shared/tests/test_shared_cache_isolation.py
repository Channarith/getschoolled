"""Cached registries must hand out copies, not their live state.

Several modules cache expensive lookups (the scenario catalog, content-pack
records, the readability word map, the presentation technique registry) and used
to return the cached object itself. One caller mutating what it received then
silently changed the result for every later caller in the process — which is how
situational-scan cues stopped appearing for every student after the first.
"""

from __future__ import annotations

import pytest


def test_get_scenario_returns_a_caller_owned_copy():
    from aoep_shared.training_agents.catalog import get_scenario, list_scenarios

    scenario_id = next(
        (s.scenario_id for s in list_scenarios(limit=200) if s.cues), None
    )
    if scenario_id is None:
        pytest.skip("no catalog scenario carries cues")

    first = get_scenario(scenario_id)
    assert first is not None and first.cues
    for cue in first.cues:
        cue.revealed = True

    second = get_scenario(scenario_id)
    assert second is not None
    assert [c.revealed for c in second.cues] == [False] * len(second.cues)
    assert second is not first


def test_load_records_copies_each_record():
    from aoep_shared.content_packs import load_records

    first = load_records("knowledge")
    if not first:
        pytest.skip("no knowledge pack records available")
    first[0]["title"] = "MUTATED-BY-CALLER"

    second = load_records("knowledge")
    assert second[0].get("title") != "MUTATED-BY-CALLER"


def test_simple_map_mutation_does_not_leak():
    from aoep_shared.readability import simplify_text
    from aoep_shared.readability import _simple_map

    _simple_map()["utilize"] = "PWNED"
    assert "PWNED" not in simplify_text("Please utilize this.")


def test_technique_registry_mutation_does_not_leak():
    from aoep_shared.presentation_skills import _pack_techniques, get_technique

    known = next(iter(_pack_techniques()))
    _pack_techniques().pop(known, None)
    assert get_technique(known) is not None


def test_a_pack_template_with_a_backslash_escape_does_not_crash_simplification():
    """re.sub interprets escapes in the REPLACEMENT; pack text must stay literal."""
    from aoep_shared.readability import _apply_word_map

    out = _apply_word_map("please make use of this", {"make use of": r"use \1"})
    assert "use" in out


def test_a_malformed_pack_template_falls_back_to_the_raw_text():
    from aoep_shared.presentation_skills import PresentationTechnique

    bad = PresentationTechnique(
        "bad", "Bad", "", "engagement", "Consider {topic} and the 50% { case.")
    assert bad.apply(topic="fractions") == "Consider {topic} and the 50% { case."

    attr = PresentationTechnique("bad2", "Bad2", "", "engagement", "See {topic.nope}.")
    assert attr.apply(topic="fractions") == "See {topic.nope}."
