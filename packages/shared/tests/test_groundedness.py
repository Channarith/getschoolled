"""Hallucination guard / groundedness tests."""

from aoep_shared.groundedness import check_grounding, guard_answer


CONTEXT = [
    "Photosynthesis: plants convert light energy into chemical energy stored in sugars.",
    "Oxygen is a byproduct of photosynthesis released into the air.",
]


def test_grounded_answer_passes():
    report = check_grounding("Plants release oxygen as a byproduct of photosynthesis.", CONTEXT)
    assert report.grounded is True
    assert report.hallucination_risk < 0.3
    assert report.unsupported == []


def test_ungrounded_answer_flagged():
    report = check_grounding(
        "The mitochondria powers muscle cells through anaerobic fermentation only.",
        CONTEXT,
    )
    assert report.grounded is False
    assert report.hallucination_risk > 0.5
    assert report.unsupported


def test_guard_replaces_ungrounded_answer():
    bad = "Photosynthesis happens in the stomach and produces nitrogen."
    safe, report = guard_answer(bad, CONTEXT, question="where does photosynthesis happen?")
    assert report.grounded is False
    # Served text is the grounded fallback, not the hallucinated claim.
    assert safe != bad
    assert "lesson" in safe.lower()


def test_guard_keeps_grounded_answer():
    good = "Oxygen is released as a byproduct of photosynthesis."
    safe, report = guard_answer(good, CONTEXT)
    assert report.grounded is True and safe == good


def test_no_context_is_high_risk():
    report = check_grounding("anything at all here", [])
    assert report.grounded is False
    assert report.hallucination_risk == 1.0
