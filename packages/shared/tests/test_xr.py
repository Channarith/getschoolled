"""XR lab rubric scoring — shared WebXR / Unity contract."""

from aoep_shared.xr import (
    XR_PROTOCOL_VERSION,
    default_lab_for_lesson,
    observation_from_dict,
    score_attempt,
)


def test_protocol_version():
    lab = default_lab_for_lesson(lesson_id="demo-1")
    assert lab.protocol_version == XR_PROTOCOL_VERSION
    assert len(lab.steps) == 3


def test_pass_and_needs_work_are_deterministic():
    lab = default_lab_for_lesson(lesson_id="l1", course_id="c1")
    pass_obs = [
        observation_from_dict(
            {"seq": 1, "action": "approach", "target_id": "station", "confidence": 0.95}
        ),
        observation_from_dict(
            {"seq": 2, "action": "grab", "target_id": "tool", "confidence": 0.9, "hold_ms": 600}
        ),
        observation_from_dict(
            {"seq": 3, "action": "confirm", "target_id": "finish", "confidence": 0.92}
        ),
    ]
    a = score_attempt(lab, pass_obs, client_kind="webxr", student_id="s1")
    b = score_attempt(lab, pass_obs, client_kind="unity_openxr", student_id="s1")
    assert a.outcome == "pass"
    assert b.outcome == "pass"
    assert a.score == b.score
    assert a.provisional is True

    weak = [
        observation_from_dict(
            {"seq": 1, "action": "approach", "target_id": "station", "confidence": 0.8}
        ),
    ]
    c = score_attempt(lab, weak, client_kind="webxr")
    d = score_attempt(lab, weak, client_kind="unity_openxr")
    assert c.outcome == "needs_work"
    assert d.outcome == "needs_work"
    assert c.score == d.score


def test_empty_observations_need_work():
    lab = default_lab_for_lesson()
    r = score_attempt(lab, [])
    assert r.outcome == "needs_work"
    assert r.score == 0.0
