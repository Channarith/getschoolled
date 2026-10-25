"""The studio tutorial must not promise anything the page does not do (and must not spell out the dance easter egg)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "src" / "theodore_course_studio"
VOICE_JS = (PKG / "voice_static" / "course_voice.js").read_text(encoding="utf-8")
PAGE_PY = (PKG / "studio_page.py").read_text(encoding="utf-8")
SOURCES = {"course_voice.js": VOICE_JS, "studio_page.py": PAGE_PY}


def tutorial_text() -> str:
    start = VOICE_JS.index("const PICTURE_STEPS")
    end = VOICE_JS.index("const tutorialSteps")
    return VOICE_JS[start:end]


# (words in the tutorial, [(file, marker that proves the behaviour exists), ...])
PROMISES = [
    ("Tap the lesson", [("studio_page.py", "on('teach-stage', 'click'"), ("studio_page.py", "proceedFromCourse")]),
    ("Double-tap the lesson", [("studio_page.py", "on('teach-stage', 'dblclick'"), ("course_voice.js", "attachTouchDoubleTap(stage)")]),
    ("Tap Sala", [("course_voice.js", "#theodore-avatar-wrap"), ("course_voice.js", "salaHandles.get(wrap)?.giggle()")]),
    ("Sala giggles", [("course_voice.js", "giggle()"), ("studio_page.py", "salaGiggle")]),
    ("turn listening on or off", [("course_voice.js", "setMuted(!muted)")]),
    ("Drag it anywhere", [("course_voice.js", "cw-grip"), ("course_voice.js", "placeCourseWidget")]),
    ("tuck it away", [("course_voice.js", "cw-collapse")]),
    ("three dots", [("course_voice.js", "cw-menu-btn")]),
    ("yellow ? button", [("course_voice.js", "sala-help")]),
    ("Captions stay off until you ask", [("course_voice.js", "captions_on")]),
]


@pytest.mark.parametrize("words,proofs", PROMISES, ids=[p[0] for p in PROMISES])
def test_each_promise_has_an_implementation(words, proofs):
    text = tutorial_text()
    assert words in text, f"tutorial no longer says {words!r}: update PROMISES so the test follows the copy"
    for filename, marker in proofs:
        assert marker in SOURCES[filename], f"tutorial promises {words!r} but {filename} has no {marker!r}"


def test_dance_is_a_secret_not_a_tutorial_step():
    text = tutorial_text().lower()
    assert "dance" not in text and "tutorial-dance" not in text
    assert "a few secrets" in text           # the only hint


def test_the_dance_easter_egg_is_wired():
    assert "matchDanceIntent(transcript" in VOICE_JS          # voice: before Q&A
    assert "observeAvatars" in VOICE_JS and "attachSalaInteractions" in VOICE_JS   # scrub: on every avatar, now or later
    assert "salaDanceMenuEnabled" in VOICE_JS                  # optional menu entry, off unless the flag is set


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_node_unit_tests_for_the_interactions_and_every_tutorial_command():
    result = subprocess.run(["node", "--test", str(Path(__file__).with_name("sala_interactions_check.mjs"))],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-1000:]
