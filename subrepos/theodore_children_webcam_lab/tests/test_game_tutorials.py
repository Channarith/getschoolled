"""Every Play Lab game must have a first-visit tutorial (Pop Quiz Toss has its own)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from theodore_children_webcam_lab.game_engine import all_game_ids

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
OWN_TUTORIAL = {"pop-quiz-toss"}


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_every_game_has_a_first_visit_tutorial():
    script = (
        "import {TUTORIALS} from './src/theodore_children_webcam_lab/static/game_tutorial.js';"
        "console.log(JSON.stringify(Object.keys(TUTORIALS)));"
    )
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script], cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    have = set(json.loads(result.stdout))
    missing = [g for g in all_game_ids() if g not in have and g not in OWN_TUTORIAL]
    assert not missing, f"games without a tutorial: {missing}"


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_game_tutorial_script_checks_pass():
    result = subprocess.run(
        [NODE, str(ROOT / "tests/game_tutorial_check.mjs")], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
