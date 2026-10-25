"""The phone detectors can fail quietly. These checks prove the fallback logic and that the page uses it."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "theodore_children_webcam_lab" / "static"
NODE = shutil.which("node")


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_detect_health_logic():
    result = subprocess.run([NODE, str(ROOT / "tests/detect_health_check.mjs")], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "detect health ok" in result.stdout


def test_game_and_diag_share_one_detector_builder():
    game = (STATIC / "app.js").read_text(encoding="utf-8")
    diag = (STATIC / "vision_diag_page.js").read_text(encoding="utf-8")
    for source in (game, diag):
        assert 'from "./vision_detectors.js"' in source
        assert "createDetectorController" in source or "createFirstWorking" in source
    # Neither builds a landmarker on its own any more: one recipe ladder, so /diag/vision is a faithful harness for the game.
    assert "FaceLandmarker.createFromOptions" not in game.replace("ctx.vision.FaceLandmarker", "")
    assert "HandLandmarker.createFromOptions" not in diag
    assert 'id="handtest"' in (ROOT / "src" / "theodore_children_webcam_lab" / "diag_page.py").read_text(encoding="utf-8")
    assert "runVariantTest" in diag and "variant-test" in diag


def test_app_wires_the_health_checks():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'from "./detect_health.js"' in js
    # The "you left the camera" pause must wait until a face was seen AND the detector is running right now.
    assert "health.presenceAllowed()" in js
    # A model that fails or stays blind walks down its recipe ladder, and failures reach the triage log.
    assert "createDetectorController" in js and "detectors?.tick()" in js
    # Models load and pre-warm while the camera prompt is open (the first iOS inference takes 7-9 s), and the status waits for the camera.
    assert "visionReady" in js and "reportVisionStatus" in js and "warmModel" in js
    assert "trace.stage(type, detail)" in js   # every controller event reaches the triage log
    detectors = (STATIC / "vision_detectors.js").read_text(encoding="utf-8")
    for event in ("detector variant", "detector found", "detector warmed", "detector env"):
        assert f'onEvent("{event}"' in detectors
    # Detection runs once per NEW camera frame, like /diag/vision (with a timer fallback for web views that never call back).
    assert "requestVideoFrameCallback" in js and "state.frameGateOn" in js
    # While tracking is unavailable the game is playable by touch, without a banner.
    assert "state.autoScreen" in js
