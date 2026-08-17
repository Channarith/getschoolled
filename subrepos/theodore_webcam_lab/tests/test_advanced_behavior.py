from __future__ import annotations

from theodore_webcam_lab.advanced_behavior import AdvancedBehaviorEngine
from theodore_webcam_lab.types import WebcamSignal
from theodore_webcam_lab.vision_tuning import VisionTuning


def _sig(**kwargs):
    base = dict(
        participant_id="learner",
        timestamp_ms=0,
        face_count=1,
        liveness_state="live",
        detector_source="face_mesh",
        motion_score=0.15,
    )
    base.update(kwargs)
    return WebcamSignal(**base)


def test_excitement_raises_curiosity_and_emits_event():
    eng = AdvancedBehaviorEngine()
    snap = eng.evaluate(
        session_id="s1",
        signal=_sig(excitement_score=0.80, interest_score=0.20, timestamp_ms=5_000),
        attention_score=0.70,
        distraction_score=0.10,
        behavior_label="focused",
        eyes_away_for_ms=0,
        eyes_closed_for_ms=0,
        yawn_for_ms=0,
        inattentive_for_ms=0,
        dominant_expression="happy",
        expression_confidence=0.8,
        suspected_cheating=False,
        tuning=VisionTuning(),
        phone_visible=False,
    )
    assert snap.excitement_score >= 0.80
    assert snap.curiosity_score > 0.4
    assert any(e.code == "excitement_burst" for e in snap.events)


def test_dozing_raises_fatigue():
    eng = AdvancedBehaviorEngine()
    snap = eng.evaluate(
        session_id="s2",
        signal=_sig(dozing_score=0.80, head_sag_rate=0.70, timestamp_ms=5_000),
        attention_score=0.40,
        distraction_score=0.20,
        behavior_label="drowsy",
        eyes_away_for_ms=0,
        eyes_closed_for_ms=0,
        yawn_for_ms=0,
        inattentive_for_ms=0,
        dominant_expression="neutral",
        expression_confidence=0.5,
        suspected_cheating=False,
        tuning=VisionTuning(),
        phone_visible=False,
    )
    assert snap.fatigue_score > 0.4
    assert snap.observatory_label == "drowsy"
