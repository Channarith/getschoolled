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


def test_app_wires_the_health_checks():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'from "./detect_health.js"' in js
    # The "you left the camera" pause must wait until a face was actually seen.
    assert "health.presenceAllowed()" in js
    # A GPU model that fails or stays blind is rebuilt on the CPU, and failures reach the triage log.
    assert "rebuildOnCpu" in js
    assert 'trace.stage("detector' in js
    # While tracking is unavailable the game is playable by touch, without a banner.
    assert "state.autoScreen" in js
