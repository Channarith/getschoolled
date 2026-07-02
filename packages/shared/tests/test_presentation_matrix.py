"""Finite presentation-mode matrix: mix-and-match delivery recipes."""

from math import prod

import numpy as np

from aoep_shared.harvest.composition import CourseComposition, NODE_CATEGORIES
from aoep_shared.meeting.presentation_matrix import (
    PRESENTATION_AXES,
    PRESENTATION_MODE_CAPACITY,
    PresentationProfile,
    arc_matrix,
    decode_presentation_mode,
    encode_presentation_mode,
    list_presentation_modes,
    recommend_presentation_modes,
    resolve_mode_index,
)


def test_capacity_is_product_of_axes():
    assert PRESENTATION_MODE_CAPACITY == prod(len(a) for a in PRESENTATION_AXES)
    assert PRESENTATION_MODE_CAPACITY == 648


def test_encode_decode_roundtrip():
    idx = encode_presentation_mode("workshop", "smart", "adaptive", "guided", "demo")
    assert decode_presentation_mode(idx) == (
        "workshop", "smart", "adaptive", "guided", "demo",
    )
    assert resolve_mode_index(idx) == idx
    assert resolve_mode_index("workshop|smart|adaptive|guided|demo") == idx


def test_presets_and_default():
    default = PresentationProfile.resolve()
    assert default.arc == "lecture"
    assert default.voice == "smart"
    assert default.time == "adaptive"
    workshop = PresentationProfile.resolve("workshop")
    assert workshop.arc == "workshop"
    drill = PresentationProfile.resolve("drill")
    assert drill.arc == "drill"


def test_single_arc_token_uses_defaults():
    p = PresentationProfile.resolve("survey")
    assert p.arc == "survey"
    assert p.voice == "smart"
    assert p.time == "adaptive"


def test_partial_pipe_fills_defaults():
    idx = resolve_mode_index("drill|smart|strict")
    arc, voice, time_policy, engage, media = decode_presentation_mode(idx)
    assert (arc, voice, time_policy, engage, media) == (
        "drill", "smart", "strict", "guided", "balanced",
    )


def test_arc_matrix_shape():
    m = arc_matrix("lecture")
    assert m.shape == (len(NODE_CATEGORIES), 6)
    assert m.sum() > 0


def test_workshop_has_more_interact_than_survey():
    w = arc_matrix("workshop")[:, 4].sum()  # interact column
    s = arc_matrix("survey")[:, 4].sum()
    assert w > s


def test_list_modes_finite():
    rows = list_presentation_modes(limit=10)
    assert len(rows) == 10
    assert rows[0]["mode_index"] == 0


def test_recommend_modes_ranks_arcs():
    comp = CourseComposition(subject="math")
    for _ in range(8):
        comp.add_node("exercise", subnode="drill")
    for _ in range(2):
        comp.add_node("concept", subnode="idea")
    rec = recommend_presentation_modes(comp, top_n=3)
    assert len(rec) == 3
    assert rec[0]["arc"] in ("drill", "workshop", "lecture", "survey", "flipped")


def test_profile_serializes():
    p = PresentationProfile.from_index(42)
    d = p.to_dict()
    assert d["mode_index"] == 42
    assert "structure" in d and "presenter" in d


def test_survey_profile_skips_try_it_in_structure():
    p = PresentationProfile.resolve("survey|smart|adaptive|guided|balanced")
    assert p.include_try_it is False
    assert p.recap_every_n == 0
