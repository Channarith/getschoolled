from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_webcam_lab.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "theodore-webcam-lab"


def test_webcam_evaluation_api_returns_solo_multiple_face_alert():
    resp = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "solo-api-1",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner",
                    "timestamp_ms": 1_000,
                    "face_count": 2,
                    "liveness_state": "live",
                    "foreground_ratio": 0.3,
                    "motion_score": 0.2,
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "solo_mode_multiple_faces:learner" in body["alerts"]


def test_voice_endpoint_falls_back_without_xai_key():
    resp = client.post(
        "/api/theodore/voice/respond",
        json={
            "class_mode": "group",
            "learner_message": "Can I get help with this biology topic?",
            "context": "Group revision",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "local-fallback"
    assert body["fallback_used"] is True


def test_voice_languages_endpoint_lists_26_supported_languages():
    resp = client.get("/api/theodore/voice/languages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 26
    assert body[0]["code"] == "en"


def test_voice_ask_question_and_absorb_audio_answer_endpoints():
    question_resp = client.post(
        "/api/theodore/voice/ask-question",
        json={
            "class_mode": "solo",
            "language_code": "de",
            "topic": "water cycle",
            "difficulty": "easy",
        },
    )
    assert question_resp.status_code == 200
    question_body = question_resp.json()
    assert question_body["language_code"] == "de"
    assert question_body["question"]

    absorb_resp = client.post(
        "/api/theodore/voice/absorb-audio-answer",
        json={
            "class_mode": "solo",
            "language_code": "de",
            "question": question_body["question"],
            "audio_transcript": "Water evaporates, forms clouds, and falls as rain.",
            "expected_answer": "evaporation condensation precipitation",
        },
    )
    assert absorb_resp.status_code == 200
    absorb_body = absorb_resp.json()
    assert absorb_body["language_code"] == "de"
    assert absorb_body["absorbed_transcript"]
    assert absorb_body["understood"] is True


def test_voice_endpoints_reject_unsupported_language():
    resp = client.post(
        "/api/theodore/voice/ask-question",
        json={
            "class_mode": "group",
            "language_code": "xx",
            "topic": "algebra",
        },
    )
    assert resp.status_code == 422


def test_webcam_expression_api_returns_happy_summary():
    resp = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-expression-1",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "learner-a",
                    "timestamp_ms": 2_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                    "expression_label": "happy",
                    "expression_confidence": 0.93,
                },
                {
                    "participant_id": "learner-b",
                    "timestamp_ms": 2_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                    "expression_label": "neutral",
                    "expression_confidence": 0.74,
                },
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["happy_participant_ids"] == ["learner-a"]
    assert body["expression_counts"] == {"happy": 1, "neutral": 1}


def test_group_webcam_api_returns_window_alerts_for_missing_and_cheating():
    first = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-window-alert-api",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "student-a",
                    "timestamp_ms": 1_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                },
                {
                    "participant_id": "student-b",
                    "timestamp_ms": 1_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                },
                {
                    "participant_id": "student-c",
                    "timestamp_ms": 1_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "phone_visible": True,
                },
            ],
            "expected_participant_ids": ["student-a", "student-b", "student-c"],
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-window-alert-api",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "student-a",
                    "timestamp_ms": 52_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                },
                {
                    "participant_id": "student-c",
                    "timestamp_ms": 52_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "phone_visible": True,
                },
            ],
            "expected_participant_ids": ["student-a", "student-b", "student-c"],
        },
    )
    assert second.status_code == 200
    body = second.json()
    windows = {item["participant_id"]: item for item in body["group_student_windows"]}
    assert windows["student-b"]["needs_intervention"] is True
    assert windows["student-c"]["suspected_cheating"] is True
    codes = {alert["code"] for alert in body["lesson_alerts"]}
    assert "group_intervention_required" in codes
    assert "student_absent" in codes
    assert "student_cheating_signal" in codes


def test_webcam_api_flags_long_eyes_away_phone_typing_pattern():
    resp = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-cheat-api",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "learner-z",
                    "timestamp_ms": 5_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "phone_visible": True,
                    "typing_activity_score": 0.95,
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    participant = body["participants"][0]
    assert participant["suspected_cheating"] is False

    # Second frame in the same session keeps eyes away long enough to cross
    # the default sustained-away grace and should now be flagged.
    resp2 = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "group-cheat-api",
            "mode": "group",
            "signals": [
                {
                    "participant_id": "learner-z",
                    "timestamp_ms": 52_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "phone_visible": True,
                    "typing_activity_score": 0.95,
                }
            ],
        },
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    p2 = body2["participants"][0]
    assert p2["suspected_cheating"] is True
    assert body2["suspected_cheating_participant_ids"] == ["learner-z"]
    assert p2["eyes_away_for_ms"] == 47_000


def test_webcam_api_detects_keyboard_typing_audio_pattern():
    first = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "audio-cheat-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-k",
                    "timestamp_ms": 1_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "keyboard_typing_audio_score": 0.88,
                }
            ],
        },
    )
    assert first.status_code == 200
    assert first.json()["participants"][0]["suspected_cheating"] is False

    second = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "audio-cheat-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-k",
                    "timestamp_ms": 50_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.5,
                    "motion_score": 0.2,
                    "gaze_frontal": 0.1,
                    "gaze_down_score": 0.9,
                    "keyboard_typing_audio_score": 0.88,
                }
            ],
        },
    )
    assert second.status_code == 200
    body = second.json()
    participant = body["participants"][0]
    assert participant["keyboard_typing_audio_detected"] is True
    assert participant["suspected_cheating"] is True
    assert participant["cheating_reasons"] == [
        "eyes_away_long",
        "keyboard_typing_audio",
    ]
    assert body["keyboard_typing_audio_participant_ids"] == ["learner-k"]


def test_webcam_game_challenge_and_attempt_flow():
    challenge_resp = client.post(
        "/api/theodore/webcam/games/challenge",
        json={
            "session_id": "game-api-1",
            "mode": "solo",
            "learning_prompt": "Explain photosynthesis in one sentence.",
            "preferred_game_type": "confidence_smile",
            "participant_ids": ["learner-g"],
        },
    )
    assert challenge_resp.status_code == 200
    challenge = challenge_resp.json()
    assert challenge["game_type"] == "confidence_smile"
    assert challenge["challenge_id"]

    attempt_resp = client.post(
        "/api/theodore/webcam/games/attempt",
        json={
            "challenge_id": challenge["challenge_id"],
            "session_id": "game-api-1",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-g",
                    "timestamp_ms": 10_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.4,
                    "motion_score": 0.1,
                    "expression_label": "happy",
                    "expression_confidence": 0.95,
                }
            ],
        },
    )
    assert attempt_resp.status_code == 200
    result = attempt_resp.json()
    assert result["passed"] is True
    assert result["score_delta"] == 12
    assert result["total_score"] >= 12
    assert result["evaluation"]["happy_participant_ids"] == ["learner-g"]


def test_webcam_game_attempt_returns_404_for_unknown_challenge():
    resp = client.post(
        "/api/theodore/webcam/games/attempt",
        json={
            "challenge_id": "challenge-missing",
            "session_id": "unknown-game",
            "mode": "solo",
            "signals": [],
        },
    )
    assert resp.status_code == 404


def test_webcam_api_pauses_training_after_no_presence_over_4_seconds():
    first = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "pause-api-1",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-p",
                    "timestamp_ms": 2_000,
                    "face_count": 0,
                    "liveness_state": "missing",
                    "foreground_ratio": 0.0,
                    "motion_score": 0.0,
                }
            ],
        },
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["training_paused"] is False

    second = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "pause-api-1",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "learner-p",
                    "timestamp_ms": 6_250,
                    "face_count": 0,
                    "liveness_state": "missing",
                    "foreground_ratio": 0.0,
                    "motion_score": 0.0,
                }
            ],
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["training_paused"] is True
    assert second_body["pause_reason"] == "no_learner_detected_over_4s"
    assert second_body["no_one_present_for_ms"] == 4_250


def test_webcam_api_pauses_when_original_user_is_replaced():
    baseline = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "original-user-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "student-main",
                    "timestamp_ms": 1_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.3,
                    "motion_score": 0.1,
                }
            ],
        },
    )
    assert baseline.status_code == 200
    body1 = baseline.json()
    assert body1["training_paused"] is False
    assert body1["original_participant_id"] == "student-main"

    replaced = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "original-user-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "student-other",
                    "timestamp_ms": 2_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.3,
                    "motion_score": 0.1,
                }
            ],
        },
    )
    assert replaced.status_code == 200
    body2 = replaced.json()
    assert body2["training_paused"] is True
    assert body2["pause_reason"] == "original_user_not_present"
    assert body2["original_user_present"] is False
    assert body2["unexpected_participant_ids"] == ["student-other"]

    resumed = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "original-user-api",
            "mode": "solo",
            "signals": [
                {
                    "participant_id": "student-main",
                    "timestamp_ms": 3_000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "foreground_ratio": 0.3,
                    "motion_score": 0.1,
                }
            ],
        },
    )
    assert resumed.status_code == 200
    body3 = resumed.json()
    assert body3["training_paused"] is False
    assert body3["original_user_present"] is True
