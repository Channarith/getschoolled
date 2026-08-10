"""World-class quality surface: knobs, telemetry, observatory series."""

from __future__ import annotations

from dataclasses import fields

from fastapi.testclient import TestClient

from theodore_webcam_lab.live_metrics import LiveMetricsStore
from theodore_webcam_lab.main import app
from theodore_webcam_lab.responsiveness_tuning import ResponsivenessTuning
from theodore_webcam_lab.types import (
    ClassEvaluation,
    ClassMode,
    ParticipantEvaluation,
    PresenceState,
    QualitySummary,
)
from theodore_webcam_lab.vision_tuning import VisionTuning
from theodore_webcam_lab.voice_tuning import VoiceTuning

client = TestClient(app)


def test_responsiveness_has_over_20_knobs():
    assert len(fields(ResponsivenessTuning)) >= 20
    assert len(ResponsivenessTuning().to_dict()) >= 20


def test_combined_knob_inventory_over_20():
    inv = client.get("/api/theodore/quality/inventory").json()
    assert inv["vision_knob_count"] >= 20
    assert inv["responsiveness_knob_count"] >= 20
    assert inv["total_knob_count"] >= 60


def test_patch_responsiveness_tuning():
    before = client.get("/api/theodore/responsiveness/tuning").json()["knobs"]
    r = client.patch(
        "/api/theodore/responsiveness/tuning",
        json={"knobs": {"eval_target_fps": 10.0, "fatigue_alert_min": 0.55}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["knobs"]["eval_target_fps"] == 10.0
    assert body["knobs"]["fatigue_alert_min"] == 0.55
    # restore balanced defaults for other tests
    client.post("/api/theodore/responsiveness/tuning/preset/balanced")
    assert before["eval_min_interval_ms"] >= 1


def test_observatory_summary_has_over_20_metrics():
    store = LiveMetricsStore()
    evaluation = ClassEvaluation(
        session_id="obs-1",
        mode=ClassMode.SOLO,
        participants=[
            ParticipantEvaluation(
                participant_id="p1",
                state=PresenceState.PRESENT,
                silhouette_detected=False,
                silhouette_streak=0,
                face_count=1,
                light_quality_score=0.8,
                image_detection_quality_score=0.75,
                expression_behavior_score=0.7,
                recognition_confidence=0.9,
                absent_for_ms=0,
                eyes_away_for_ms=0,
                advanced_behavior={
                    "engagement_index": 0.81,
                    "fatigue_score": 0.2,
                    "confusion_score": 0.15,
                    "multitask_score": 0.1,
                    "flow_score": 0.7,
                    "observatory_label": "focused",
                },
            )
        ],
        absent_participant_ids=[],
        silhouette_participant_ids=[],
        happy_participant_ids=["p1"],
        keyboard_typing_audio_participant_ids=[],
        suspected_cheating_participant_ids=[],
        quality_summary=QualitySummary(
            participants_count=1,
            avg_light_quality_score=0.8,
            avg_image_detection_quality_score=0.75,
            avg_expression_behavior_score=0.7,
            avg_recognition_confidence=0.9,
        ),
        expression_counts={"happy": 1},
        alerts=[],
    )
    store.record(session_id="obs-1", evaluation=evaluation, updated_at_ms=1000)
    store.record(session_id="obs-1", evaluation=evaluation, updated_at_ms=1200)
    snap = store.snapshot("obs-1")
    assert len(snap.observatory_summary) >= 20
    assert snap.participants[0].engagement_index[-1] == 0.81
    assert snap.participants[0].fatigue_score[-1] == 0.2
    assert snap.observatory_summary["avg_engagement_index"] == 0.81
    assert snap.observatory_summary["frames_recorded"] == 2


def test_vision_and_voice_knob_floors():
    assert len(VisionTuning().to_dict()) >= 20
    assert len(VoiceTuning().to_dict()) >= 10
