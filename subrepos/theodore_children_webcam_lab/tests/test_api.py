from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theodore_children_webcam_lab.analytics import sanitize_event
from theodore_children_webcam_lab.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


def test_page_exposes_core_games_privacy_and_fun_ui():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    for text in (
        "Oh behave",
        "Fruit cut",
        "Air drums",
        "Pop balloons",
        "Fun 0",
        "No recordings or Face ID",
        "/static/app.js",
    ):
        assert text in html


def test_health_and_content_describe_private_browser_runtime():
    health = client.get("/health").json()
    assert health["camera_uploads"] is False
    assert health["audio_uploads"] is False
    assert health["face_id"] is False
    content = client.get("/api/child/content").json()
    assert len(content["letters"]) == 26
    assert {"cuddly", "hero", "mix"} == set(content["themes"])
    assert {"fruit-cut", "oh-behave", "trace-letter"} <= set(content["games"])


def test_pronounce_reuses_text_only_music_lab_approach():
    response = client.post(
        "/api/child/pronounce",
        json={"target": "B", "heard": "bee", "kind": "letter"},
    )
    assert response.status_code == 200
    assert response.json()["passed"] is True


def test_analytics_is_aggregate_only_and_rejects_private_fields():
    event = {
        "activity_id": "fruit-cut",
        "age_band": "7-10",
        "outcome": "success",
        "attempts": 1,
        "duration_ms": 1200,
        "fun_score": 91,
        "theme_pack": "hero",
    }
    assert client.post("/api/child/analytics", json=event).status_code == 200
    summary = client.get("/api/child/analytics/summary").json()
    assert summary["activities"]["fruit-cut"]["plays"] >= 1
    assert "events" not in summary
    with pytest.raises(ValueError):
        sanitize_event(event | {"video": "base64"})
    with pytest.raises(ValueError):
        sanitize_event(event | {"transcript": "apple"})
    forbidden = client.post("/api/child/analytics", json=event | {"video": "nope"})
    assert forbidden.status_code == 422
    junk = sanitize_event(event | {"components": {"play": 9, "secret": {"x": 1}}})
    assert junk["components"] == {"play": 9}


def test_static_javascript_has_expected_privacy_and_game_guards():
    script = (ROOT / "src/theodore_children_webcam_lab/static/app.js").read_text()
    assert "getUserMedia" in script
    assert "numHands:2" in script
    assert "outputFaceBlendshapes:true" in script
    assert "SpeechRecognition" in script
    assert "video.currentTime===state.lastVideoTime" in script
    assert "face.detectForVideo" in script
    assert "hands.detectForVideo" in script
    assert 'fetch("/api/child/analytics"' in script
    assert "MediaRecorder" not in script
    assert "canvas.toDataURL" not in script
    assert "roundId" in script
    assert "cancelSpeech" in script
    assert 'state.game!=="say-letter"' in script
    assert "OBJECT_GAMES.has(state.game)" in script
    assert "esc(id.replaceAll" in script
    assert "tipToWrist<0.22" in script
    assert "Hold still like a statue" in script


def test_static_javascript_parses_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = ROOT / "src/theodore_children_webcam_lab/static/app.js"
    result = subprocess.run(
        [node, "--check", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
