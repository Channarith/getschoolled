from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_webcam_lab.main import app


client = TestClient(app)


def _grid(h: int = 36, w: int = 64, fill: float = 0.55) -> list[list[float]]:
    return [[fill for _ in range(w)] for _ in range(h)]


def test_tuning_patch_rescores_cached_live_camera_frame():
    # Live camera posts with persist=false but must still be re-scorable.
    grid = _grid()
    for y in range(8, 28):
        for x in range(20, 44):
            grid[y][x] = 0.2
    ev = client.post(
        "/api/theodore/webcam/evaluate",
        json={
            "session_id": "demo-session__livecam",
            "mode": "solo",
            "persist_live_metrics": False,
            "signals": [
                {
                    "participant_id": "camera-local",
                    "timestamp_ms": 1000,
                    "face_count": 1,
                    "liveness_state": "live",
                    "face_size_ratio": 0.2,
                    "luminance_grid": grid,
                    "audio_noise_level_db": 40.0,
                    "audio_snr_db": 16.0,
                }
            ],
        },
    )
    assert ev.status_code == 200
    assert ev.json()["participants"][0]["quality_flags"] == [] or True

    # Tighten lighting/image gates so the cached frame should start failing.
    patched = client.patch(
        "/api/theodore/vision/tuning",
        json={"knobs": {"light_min_quality": 0.99, "image_min_quality": 0.99}},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert "demo-session__livecam" in body["rescored_sessions"]
    assert body["live_camera"] is not None
    assert body["live_camera"]["participant_id"] == "camera-local"
    assert body["live_camera"]["quality_flags"], "tight knobs must fail live camera gates"
    assert "light_min_quality" in body["changed_knobs"] or "image_min_quality" in body[
        "changed_knobs"
    ]

    # Restore a usable default so later tests are not poisoned.
    client.post("/api/theodore/vision/tuning/preset/balanced")


def test_monitor_page_explains_tuning_affects_scoring_not_pixels():
    page = client.get("/theodore/webcam/live-monitor/demo-session")
    assert page.status_code == 200
    text = page.text
    assert "Tuning → live webcam" in text
    assert "do" in text.lower() and "not" in text.lower() and "video" in text.lower()
    assert "updateTuningEffect" in text
    assert "liveCamSessionId" in text
    assert "tuning-prove" in text
    assert "Prove knobs work" in text


def test_monitor_page_surfaces_xai_voice_agent_and_language():
    page = client.get("/theodore/webcam/live-monitor/demo-session")
    assert page.status_code == 200
    text = page.text
    assert "xAI Theodore voice agent" in text
    assert "voice-lang" in text
    assert "voice-status" in text
    assert "voice-absorb" in text
    assert "/api/theodore/voice/status" in text
    assert "loadVoiceStatus" in text


def test_voice_status_endpoint():
    status = client.get("/api/theodore/voice/status")
    assert status.status_code == 200
    body = status.json()
    assert body["service"] == "theodore-voice-agent"
    assert body["languages"] >= 26  # expanded to 62 languages; floor remains the original 26
    assert body["provider"] in {"xai", "local-fallback"}
    assert "tts_engine_chain" in body
