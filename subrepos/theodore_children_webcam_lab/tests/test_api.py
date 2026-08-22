from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theodore_children_webcam_lab.analytics import sanitize_event
from theodore_children_webcam_lab.children_page import render_children_page
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
        "Vision testing overlays",
        "Face contour",
        "Hand skeletons",
        "Distance & measurements",
        'id="guide-layer"',
        'id="vision-readout"',
        'id="show-guide"',
        'id="show-face"',
        'id="show-hands"',
        'id="show-trail"',
        'id="show-measures"',
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
    assert "Hold still like a statue" in script
    # Gesture thresholds must be hand-relative, never absolute frame distances.
    assert "tipToWrist<0.22" not in script
    assert "FIST_MAX_PALMS" in script
    assert "vision_math.js" in script
    # The stage box is measured on resize, not per landmark per frame.
    assert "stage.clientWidth" not in script
    assert "stage.clientHeight" not in script
    # Every vision input is visible and independently switchable while testing.
    for toggle in ("show-face", "show-hands", "show-trail", "show-measures"):
        assert f'switchedOn("{toggle}")' in script
        # Reading .checked directly throws when the page predates the control,
        # which is exactly what a dev server serving new script over an old
        # HTML shell does; the helper defaults the overlay on instead.
        assert f'$("{toggle}").checked' not in script
    assert "renderVisionReadout" in script
    assert "faceDistanceLabel" in script
    assert "traceProgress" in script
    assert "updateGuideLayer" in script
    # Missing optional self-hosted vision assets must not create a noisy 404.
    assert 'fetch("/vendor/vision/tasks-vision.mjs"' not in script
    assert 'fetch("/health")' in script
    # One failed server render disables it for the session; later prompts use
    # browser speech instead of producing a console full of repeated 501s.
    assert "state.serverTts=false" in script
    assert 'fetch("/api/tts/status")' in script
    assert "if (state.serverTts === false) return" in script
    assert 'stage?.classList.add("demo")' in script or 'stage.classList.add("demo")' in script
    assert 'target.classList.contains("hidden")' in script
    assert 'get("demo")==="1"' in script


def test_the_page_survives_new_script_against_an_older_shell():
    """A running dev server serves updated static files but its own old HTML.

    Static mounts read from disk per request, so an already-running process
    hands the browser a new ``app.js`` while still rendering the page shell it
    was started with. Every new-node access must therefore tolerate the node
    being absent, or the lab dies on load with a null dereference and the only
    visible symptom is unrelated console noise.
    """
    script = (ROOT / "src/theodore_children_webcam_lab/static/app.js").read_text()
    optional_nodes = (
        "guide-layer",
        "guide-glyph",
        "vision-readout",
        "show-guide",
    )
    for node in optional_nodes:
        for unguarded in (f'$("{node}").classList', f'$("{node}").textContent',
                          f'$("{node}").checked', f'$("{node}").addEventListener'):
            assert unguarded not in script, f"{unguarded} throws without {node}"
    # Readout text goes through the null-tolerant setter, never a raw assignment.
    for readout in ("face", "hand", "distance", "motion", "trace", "game"):
        assert f'$("{readout}-readout").textContent=' not in script
        assert f'setText("{readout}-readout"' in script
    assert "switchedOn = (id) =>" in script
    assert "setText = (id, text) =>" in script


def test_updated_front_end_code_busts_the_browser_cache():
    """Otherwise a cached app.js makes every fix look like it did nothing."""
    from theodore_children_webcam_lab.main import _asset_tag

    tag = _asset_tag()
    html = render_children_page(tag)
    assert f'src="/static/app.js?v={tag}"' in html
    assert f'href="/static/app.css?v={tag}"' in html
    assert "__ASSET_TAG__" not in html

    # The tag must follow the source, not just the released version, because
    # edits between releases leave the version untouched.
    static = ROOT / "src/theodore_children_webcam_lab/static/app.js"
    original = static.read_bytes()
    try:
        static.write_bytes(original + b"\n// touched\n")
        assert _asset_tag() != tag
    finally:
        static.write_bytes(original)
    assert _asset_tag() == tag


def test_blow_a_kiss_needs_a_tracked_face_for_both_steps():
    """Losing the face used to satisfy step two, so the round passed itself."""
    script = (ROOT / "src/theodore_children_webcam_lab/static/app.js").read_text()
    kiss = script.split('state.game==="blow-kiss"')[1].split("make-pose")[0]
    # The old success condition was "hand is no longer near", which a dropped
    # face also satisfied. It must now require outward travel instead.
    assert "!handNearFace" not in kiss
    assert "KISS_AWAY_FACES" in kiss
    assert "if (!state.faceData)" in kiss


def test_gesture_geometry_is_distance_invariant():
    """Run the real geometry: same pose, different camera distances.

    A fist stopped being recognised once the hand filled more than ~0.22 of the
    frame, because the threshold was an absolute distance in a normalised
    frame. These assertions execute the shipped module rather than grepping it.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    check = ROOT / "tests/vision_math_check.mjs"
    result = subprocess.run(
        [node, str(check)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "vision geometry OK" in result.stdout


@pytest.mark.parametrize(
    "script_name", ["app.js", "vision_math.js"]
)
def test_static_javascript_parses_with_node(script_name):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = ROOT / "src/theodore_children_webcam_lab/static" / script_name
    result = subprocess.run(
        [node, "--check", str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
