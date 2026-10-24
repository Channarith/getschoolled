"""Every Play Lab game must have a first-visit tutorial (Pop Quiz Toss has its own)."""

from __future__ import annotations

import json
import re
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


def test_pop_quiz_tutorial_labels_are_template_strings_and_art_load_is_shared():
    game = (ROOT / "src/theodore_children_webcam_lab/static/pop_quiz_game.js").read_text()
    # A "${...}" inside a single-quoted string is printed literally (it once showed ${words.prev} on a button).
    for number, line in enumerate(game.splitlines(), 1):
        if re.search(r"'<[^'`\n]*\$\{[^'`\n]*'", line):
            raise AssertionError(f"pop_quiz_game.js:{number} interpolates inside a single-quoted string")
    # The tutorial and the round both ask for art; they must share one pending fetch, not an empty set.
    assert "pq.artLoad" in game


def test_art_pack_is_listed_in_the_manifest_and_packaged():
    art = ROOT / "src/theodore_children_webcam_lab/static/art"
    manifest = json.loads((art / "manifest.json").read_text())
    names = set(manifest["assets"])
    assert {"sala-cheer", "ball-fire", "target-pins", "bg-teddy", "tut-throw", "win-card"} <= names
    for name, meta in manifest["assets"].items():
        file = art / f"{name}.webp"
        assert file.is_file(), name
        assert file.stat().st_size == meta["bytes"] <= 200_000, name
    assert "static/art/*" in (ROOT / "pyproject.toml").read_text()


def test_question_timer_pauses_when_the_learner_is_away_and_touch_side_is_sticky():
    game = (ROOT / "src/theodore_children_webcam_lab/static/pop_quiz_game.js").read_text()
    paused = game[game.index("function timerPaused") : game.index("function stopQuestionTimer")]
    # The lab says "the lesson is paused" when the learner leaves the camera (state.voiceAway).
    assert "voiceAway" in paused and "flying" in paused and "hearingUntil" in paused
    # One touch press stays on one tracker even when the swipe crosses the middle of the screen.
    assert "pq.screenSide" in game
