"""Live monitor UX regressions: demo seed, camera isolation, alerts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_webcam_lab.demo_seed import build_demo_payload
from theodore_webcam_lab.main import app

client = TestClient(app)


def test_demo_seed_shows_cheating_silhouette_and_alerts():
    seeded = client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-demo-1", "frames": 12, "scenario": "group"},
    )
    assert seeded.status_code == 200
    body = seeded.json()
    assert body["scenario"] == "group"
    assert set(body["participant_ids"]) == {"student-a", "student-b", "student-c"}
    assert "student-b" in body["cheating_participant_ids"]
    assert "student-c" in body["silhouette_participant_ids"]
    assert "student_cheating_signal" in body["lesson_alert_codes"]
    assert "student_silhouette" in body["lesson_alert_codes"]

    metrics = client.get("/api/theodore/webcam/live-metrics/ux-demo-1")
    assert metrics.status_code == 200
    snap = metrics.json()
    ids = {p["participant_id"] for p in snap["participants"]}
    assert ids == {"student-a", "student-b", "student-c"}
    by_id = {p["participant_id"]: p["latest"] for p in snap["participants"]}
    assert by_id["student-b"]["suspected_cheating"] is True
    assert "phone_visible" in by_id["student-b"]["cheating_reasons"]
    assert by_id["student-c"]["silhouette_detected"] is True
    assert snap["group_student_windows"]
    assert snap["suspected_cheating_participant_ids"] == ["student-b"]
    assert snap["silhouette_participant_ids"] == ["student-c"]


def test_solo_demo_seed_has_one_student():
    """One webcam ⇒ one demo learner; group demo is opt-in."""
    seeded = client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-solo-1", "frames": 8, "scenario": "solo"},
    )
    assert seeded.status_code == 200
    body = seeded.json()
    assert body["scenario"] == "solo"
    assert body["mode"] == "solo"
    assert body["participant_ids"] == ["learner"]
    assert body["cheating_participant_ids"] == []
    assert body["silhouette_participant_ids"] == []

    snap = client.get("/api/theodore/webcam/live-metrics/ux-solo-1").json()
    assert {p["participant_id"] for p in snap["participants"]} == {"learner"}
    assert snap["mode"] == "solo"


def test_camera_local_evaluate_does_not_clobber_group_demo_metrics():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-demo-2", "frames": 8},
    )
    before = client.get("/api/theodore/webcam/live-metrics/ux-demo-2").json()
    assert {p["participant_id"] for p in before["participants"]} == {
        "student-a",
        "student-b",
        "student-c",
    }

    cam = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "ux-demo-2",
            "mode": "solo",
            "persist_live_metrics": False,
            "signals": [
                {
                    "participant_id": "camera-local",
                    "timestamp_ms": 99_000,
                    "face_count": 0,
                    "foreground_ratio": 0.97,
                    "motion_score": 0.02,
                    "liveness_state": "unknown",
                }
            ],
        },
    )
    assert cam.status_code == 200
    assert cam.json()["participants"][0]["participant_id"] == "camera-local"

    after = client.get("/api/theodore/webcam/live-metrics/ux-demo-2").json()
    assert {p["participant_id"] for p in after["participants"]} == {
        "student-a",
        "student-b",
        "student-c",
    }
    assert "camera-local" not in {
        p["participant_id"] for p in after["participants"]
    }


def test_lesson_alert_acknowledge_is_recorded():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-demo-3", "frames": 8},
    )
    ack = client.post(
        "/api/theodore/webcam/alerts/acknowledge",
        json={
            "session_id": "ux-demo-3",
            "code": "student_cheating_signal",
            "participant_id": "student-b",
        },
    )
    assert ack.status_code == 200
    assert "student_cheating_signal:student-b" in ack.json()["acknowledged_alert_keys"]
    metrics = client.get("/api/theodore/webcam/live-metrics/ux-demo-3").json()
    assert "student_cheating_signal:student-b" in metrics["acknowledged_alert_keys"]


def test_monitor_page_includes_silhouette_and_demo_controls():
    page = client.get("/theodore/webcam/live-monitor/demo-session")
    assert page.status_code == 200
    text = page.text
    assert "Load solo demo (1 student)" in text
    assert "Load group demo (3 students)" in text
    assert "demo-seed-group" in text
    assert "simulated" in text.lower() or "Simulated" in text
    assert "Silhouette demo" in text
    assert "cam-overlay" in text
    assert "aspect-ratio: 16 / 9" in text
    assert "cam-res" in text
    assert "cam-sil-toggle" in text
    assert "cam-pause-overlay" in text
    assert "notifyLiveAway" in text
    assert "LIVE_AWAY_NOTIFY_MS" in text
    assert "liveCamTimestampMs" in text
    assert "LIVE_AWAY_REANNOUNCE_MS" in text
    assert "no_learner_detected" in text
    assert "PAUSED" in text
    assert "banner.pause" in text
    assert "Guide on" in text
    assert "full camera frame" in text or "full frame is scanned" in text
    assert "framing guide" in text
    assert "cam-contour-toggle" in text
    assert "Contours on" in text
    assert "trackFaceContoursAndMood" in text
    assert "emotionFromBlendshapes" in text
    assert "facial-hud" in text
    assert "facial-dist" in text
    assert "sampleLidarDistanceMeters" in text
    assert "sampleMicAudio" in text
    assert "audio-noise" in text
    assert "noiseSuppression" in text
    assert "estimateFacialFromGrid" in text
    assert "updateFacialHud" in text
    assert "updateAudioHud" in text
    assert "drawSilhouetteGuide" in text
    assert "silhouetteGuideOn" in text
    assert "you do not need to match this outline" in text
    assert "1920" in text and "1080" in text
    assert "face size in frame" in text or "LiDAR if available" in text
    assert "Run lesson action" in text
    assert "persist_live_metrics: false" in text
    assert "Timing policy" in text
    assert any(phrase in text for phrase in ("Try Theodore", "Theodore voice", "xAI Theodore"))
    assert "Issue challenge" in text
    assert "image_min_quality" in text
    assert "silhouette_foreground_threshold" in text
    assert "demo-degraded" in text
    assert "/api/theodore/webcam/alerts/action" in text


def test_lesson_alert_action_sends_private_message_and_game():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-action-1", "frames": 8},
    )
    acted = client.post(
        "/api/theodore/webcam/alerts/action",
        json={
            "session_id": "ux-action-1",
            "code": "student_cheating_signal",
            "action": "notify_student_privately_and_reinforce_integrity",
            "participant_id": "student-b",
            "message": "test",
        },
    )
    assert acted.status_code == 200
    body = acted.json()
    assert body["ok"] is True
    assert "student-b" in body["summary"]
    assert body["details"]["challenge_id"]
    presentation = body["details"]["presentation"]
    assert presentation["visual_effect"] == "shield"
    assert presentation["visual_title"] == "Integrity focus challenge"
    assert "Student B" in presentation["speech_text"]
    metrics = client.get("/api/theodore/webcam/live-metrics/ux-action-1").json()
    assert metrics["private_messages"]
    assert any("Integrity" in m["body"] for m in metrics["private_messages"])
    assert "student_cheating_signal:student-b" in metrics["acknowledged_alert_keys"]


def test_lesson_actions_render_and_speak_as_theodore():
    page = client.get("/theodore/webcam/live-monitor/action-stage")
    assert page.status_code == 200
    text = page.text
    assert 'id="theodore-action"' in text
    assert 'id="theodore-action-speech"' in text
    assert 'id="theodore-action-speak"' in text
    assert "presentTheodoreAction" in text
    assert "speakCurrentAction" in text
    assert "speakTheodore(currentActionSpeech" in text
    assert "theodore-action show effect-" in text
    assert "theodore-action.speaking .theodore-mouth" in text
    assert "Theodore is taking action" in text


def test_face_mesh_loads_cdn_first_without_local_assets():
    """Regression: making the self-hosted /vendor/vision path first meant every
    session 404'd on it before reaching the CDN, so the face mesh — and the
    contours + mood cards it feeds — silently stopped appearing. With no local
    assets the page must say so and try the CDN, not the dead local path first."""
    page = client.get("/theodore/webcam/live-monitor/mesh-order").text
    assert "__VISION_LOCAL_ASSETS__" not in page, "server left the flag unsubstituted"
    assert "const VISION_LOCAL_ASSETS = false;" in page
    # The self-hosted source is only pushed when the flag is true.
    assert "if (VISION_LOCAL_ASSETS) {" in page
    # The CDN source is unconditional so it always loads out of the box.
    assert "cdn.jsdelivr.net/npm/@mediapipe/tasks-vision" in page


def test_coarse_mode_still_draws_a_contour_and_mood():
    """Regression: when the mesh cannot load and the browser has no FaceDetector,
    the accuracy pass left the panel blank. The coarse grid path must still draw
    an approximate outline (fallbackBox) and keep a mood label so the operator
    sees live face tracking — clearly badged 'coarse', not landmark-accurate."""
    page = client.get("/theodore/webcam/live-monitor/coarse-contour").text
    # Grid estimator exposes a normalised box for the coarse overlay.
    assert "grid_box" in page
    # estimateFacialExperience promotes it into a drawable fallback contour.
    assert "fallbackBox: {" in page
    assert "facial.source === 'coarse'" in page
    # The coarse oval is drawn by the existing fallback renderer.
    assert "function drawDetectorFaceContour" in page


def test_policy_timing_endpoint_and_all_vision_knobs_listed():
    policy = client.get("/api/theodore/vision/policy")
    assert policy.status_code == 200
    assert "gaze_away_grace_ms" in policy.json()["knobs"]
    patched = client.patch(
        "/api/theodore/vision/policy",
        json={"knobs": {"gaze_away_grace_ms": 2000}},
    )
    assert patched.status_code == 200
    assert patched.json()["knobs"]["gaze_away_grace_ms"] == 2000
    # restore
    client.patch("/api/theodore/vision/policy", json={"knobs": {"gaze_away_grace_ms": 45000}})

    tuning = client.get("/api/theodore/vision/tuning").json()["knobs"]
    page = client.get("/theodore/webcam/live-monitor/demo-session").text
    for name in tuning:
        assert name in page, f"vision knob {name} missing from monitor UI"


def test_build_demo_payload_accelerates_cheating_timeline():
    first = build_demo_payload(session_id="x", step=0)
    later = build_demo_payload(session_id="x", step=5)
    b0 = next(s for s in first["signals"] if s["participant_id"] == "student-b")
    b5 = next(s for s in later["signals"] if s["participant_id"] == "student-b")
    assert b5["timestamp_ms"] - b0["timestamp_ms"] >= 45_000
    sil = next(s for s in later["signals"] if s["participant_id"] == "student-c")
    assert sil["face_count"] == 0
    assert sil["foreground_ratio"] >= 0.95


def test_vision_preset_rescores_demo_session_immediately():
    client.post(
        "/api/theodore/webcam/demo/seed",
        json={"session_id": "ux-preset-1", "frames": 8},
    )
    before = client.get("/api/theodore/webcam/live-metrics/ux-preset-1").json()
    before_flags = before["quality_summary"]["quality_flag_counts"]
    before_dist = {
        p["participant_id"]: p["latest"]["distance_from_camera_m"]
        for p in before["participants"]
    }

    applied = client.post("/api/theodore/vision/tuning/preset/high_accuracy")
    assert applied.status_code == 200
    body = applied.json()
    assert "ux-preset-1" in body["rescored_sessions"]
    assert body["changed_knobs"]
    assert "light_min_quality" in body["changed_knobs"]

    after = client.get("/api/theodore/webcam/live-metrics/ux-preset-1").json()
    after_flags = after["quality_summary"]["quality_flag_counts"]
    # high_accuracy raises light/sharpness floors so student-b should trip gates.
    assert after_flags.get("lighting_below_min_quality", 0) >= 1 or after_flags != before_flags

    wide = client.post("/api/theodore/vision/tuning/preset/wide_angle_laptop")
    assert wide.status_code == 200
    after_wide = client.get("/api/theodore/webcam/live-metrics/ux-preset-1").json()
    after_dist = {
        p["participant_id"]: p["latest"]["distance_from_camera_m"]
        for p in after_wide["participants"]
    }
    assert after_dist["student-a"] != before_dist["student-a"]

    client.post("/api/theodore/vision/tuning/preset/balanced")


def test_synthetic_sources_render_to_the_visible_canvas():
    """Regression: "Test pattern" drew its bars straight into the hidden 64x36
    analysis canvas and left the empty <video> showing, so the operator saw a
    black box while the gates scored a pattern nobody could see."""
    text = client.get("/theodore/webcam/live-monitor/demo-session").text
    assert "function paintTestPattern" in text
    assert "function paintSilhouettePattern" in text
    # Both synthetic modes must sample the very canvas that is shown on screen.
    assert text.count("ctx.drawImage(patternCanvas, 0, 0, GRID_W, GRID_H)") == 2
    # One bar per analysis column keeps the downsample identical to the old grid.
    assert "const barW = w / GRID_W;" in text
    assert "synthetic frame, no face to read" in text
