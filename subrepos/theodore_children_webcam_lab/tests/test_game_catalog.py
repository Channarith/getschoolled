"""Every advertised Play Lab game must exist in the menu, API, and game loop."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from fastapi.testclient import TestClient

from theodore_children_webcam_lab.children_page import render_children_page
from theodore_children_webcam_lab.game_engine import (
    GAME_MENU,
    PICTURE_EMOJI,
    PICTURE_WORDS,
    all_game_ids,
)
from theodore_children_webcam_lab.main import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)

OBJECT_GAMES = {"fruit-cut", "balloon", "fish", "popcorn"}
AUDIO_GAMES = {
    "repeat-after-me", "pronounce-word", "rhyme-time", "listen-answer",
    "missing-word", "opposites", "explain-it", "sum-it-up", "prove-it",
    "story-order", "how-many", "same-or-different", "finish-the-line",
    "spell-aloud",
}
LOOP = {
    "trace-letter": "updateTrace",
    "trace-picture": "updateTrace",
    "color-picture": "updatePicturePlay",
    "connect-dots": "updatePicturePlay",
    "trace-outline": "updatePicturePlay",
    "say-letter": "checkSpeech",
    "repeat-after-me": "checkSpeech",
    "pronounce-word": "checkSpeech",
    "rhyme-time": "checkSpeech",
    "listen-answer": "checkSpeech",
    "missing-word": "checkSpeech",
    "opposites": "checkSpeech",
    "explain-it": "checkSpeech",
    "sum-it-up": "checkSpeech",
    "prove-it": "checkSpeech",
    "story-order": "checkSpeech",
    "how-many": "checkSpeech",
    "same-or-different": "checkSpeech",
    "finish-the-line": "checkSpeech",
    "spell-aloud": "checkSpeech",
    "oh-behave": "updateGestureGame",
    "heart": "updateGestureGame",
    "idea": "updateGestureGame",
    "fist-bump": "updateGestureGame",
    "wow": "updateGestureGame",
    "blow-kiss": "updateGestureGame",
    "wink": "updateGestureGame",
    "make-pose": "updateGestureGame",
    "balloon": "updateObjectGame",
    "fish": "updateObjectGame",
    "popcorn": "updateObjectGame",
    "fruit-cut": "updateObjectGame",
    "air-drums": "updateGestureGame",
    "bird-flap": "updateGestureGame",
    "head-bop": "updateGestureGame",
    "face-chase": "updateGestureGame",
    "stand-sit": "updateGestureGame",
    "dance-freeze": "updateGestureGame",
    "rainbow-reach": "updateGestureGame",
}


def _js() -> str:
    return (ROOT / "src/theodore_children_webcam_lab/static/app.js").read_text()


def _js_game_list(script: str) -> list[str]:
    match = re.search(r"const GAMES = \[([^\]]+)\]", script, re.S)
    assert match, "app.js must declare const GAMES = [...]"
    return ast.literal_eval("[" + match.group(1) + "]")


def test_every_menu_game_is_in_the_api_and_the_game_loop():
    catalog = list(all_game_ids())
    assert catalog == [game_id for _group, games in GAME_MENU for game_id, _ in games]
    assert set(catalog) == set(LOOP)
    assert len(catalog) == len(LOOP) == 39
    assert AUDIO_GAMES <= set(catalog)

    html = render_children_page("test")
    assert 'id="chrome-toggle"' in html
    html_ids = re.findall(r'<option value="([^"]+)">', html)
    html_ids = [item for item in html_ids if item in LOOP]
    assert html_ids == catalog

    api = client.get("/api/child/content").json()["games"]
    assert api == catalog

    script = _js()
    assert _js_game_list(script) == catalog
    choose = script.split("function chooseGame()")[1].split("function randomRegion()")[0]
    gesture = script.split("function updateGestureGame")[1].split("function isDancing()")[0]
    for game_id in catalog:
        if game_id in OBJECT_GAMES:
            assert "OBJECT_GAMES.has(state.game)" in choose, game_id
        elif game_id in AUDIO_GAMES:
            assert "AUDIO_GAMES.has(state.game)" in choose, game_id
        else:
            assert f'state.game==="{game_id}"' in choose, game_id
        assert f"function {LOOP[game_id]}" in script
        if LOOP[game_id] == "updateGestureGame":
            assert f'state.game==="{game_id}"' in gesture, game_id
        if LOOP[game_id] == "updateTrace":
            assert f'"{game_id}"' in script.split("function updateTrace()")[1].split(
                "function faceDistanceLabel"
            )[0]
        if LOOP[game_id] == "checkSpeech":
            assert "function isAudioGame" in script


def test_every_picture_word_has_a_glyph_on_both_sides():
    script = _js()
    assert set(PICTURE_EMOJI) == set(PICTURE_WORDS.values())
    for word, glyph in PICTURE_EMOJI.items():
        assert glyph in script
        assert word in script


def test_coloring_scratches_and_phones_can_switch_touch():
    html = render_children_page("test")
    assert 'id="touch-mode"' in html
    script = _js()
    assert "function screenTouch" in script
    assert "scratchCoverage" in script
    assert "fingersPointed" in script
    assert "state.painted[index] = true" not in script
    css = (ROOT / "src/theodore_children_webcam_lab/static/app.css").read_text()
    assert "body:not(.phone-play) #touch-mode" in css


def test_pointer_demo_listens_on_the_stage_not_the_dead_canvas():
    script = _js()
    assert 'stage?.addEventListener("pointermove"' in script
    assert "applyDemoPointer(event)" in script
    assert 'stage?.addEventListener("pointerdown"' in script
    assert "salareen-telemetry" in script
    assert "phone-play" in script
    assert "syntheticHand" in script
    css = (ROOT / "src/theodore_children_webcam_lab/static/app.css").read_text()
    assert ".stage.demo" in css
    assert ".stage video" in css and "pointer-events:none" in css


CONTROL_FLAGS = ("letter", "undo", "mic", "typed", "check", "hear", "words", "play")
DRAWING_GAMES = (
    "trace-letter", "trace-picture", "color-picture", "connect-dots", "trace-outline",
)
READ_ALONG_GAMES = (
    "repeat-after-me", "pronounce-word", "rhyme-time", "finish-the-line", "spell-aloud",
)


def _control_map(script: str) -> dict[str, dict[str, bool]]:
    match = re.search(r"const GAME_CONTROLS = \{([\s\S]*?)\n\};", script)
    assert match, "GAME_CONTROLS must be one explicit map"
    found: dict[str, dict[str, bool]] = {}
    for game_id, block in re.findall(r'"([a-z0-9-]+)":\s*\{([^}]*)\}', match.group(1)):
        flags = {
            key: value == "true"
            for key, value in re.findall(r"(\w+)\s*:\s*(true|false)", block)
        }
        found[game_id] = flags
    return found


def test_each_game_has_its_own_controls_and_launch_is_not_trace_letter():
    script = _js()
    controls = _control_map(script)
    catalog = list(all_game_ids())
    assert list(controls) == catalog
    assert "return GAME_CONTROLS[gameId] || NO_CONTROLS" in script
    assert "hear:false" in script.split("const NO_CONTROLS = ")[1].split(";")[0]
    assert "words:false" in script.split("const NO_CONTROLS = ")[1].split(";")[0]

    for game_id, row in controls.items():
        assert set(row) == set(CONTROL_FLAGS), game_id
        assert row["play"] is True and row["hear"] is True

    for game_id in DRAWING_GAMES:
        assert controls[game_id]["letter"] and controls[game_id]["undo"]
        assert controls[game_id]["mic"] is False and controls[game_id]["words"] is False
    say = controls["say-letter"]
    assert say["letter"] and say["mic"] and say["typed"] and say["check"]
    assert say["undo"] is False and say["words"] is False
    for game_id in AUDIO_GAMES:
        row = controls[game_id]
        assert row["mic"] and row["typed"] and row["check"] and row["words"]
        assert row["letter"] is False and row["undo"] is False
    for game_id in READ_ALONG_GAMES:
        assert controls[game_id]["words"] is True
    gesture = [
        game_id for game_id in catalog
        if game_id not in DRAWING_GAMES and game_id != "say-letter" and game_id not in AUDIO_GAMES
    ]
    assert {"heart", "fist-bump", "fruit-cut", "dance-freeze", "oh-behave"} <= set(gesture)
    for game_id in gesture:
        row = controls[game_id]
        assert row["words"] is False, game_id
        assert row["letter"] is False and row["mic"] is False
        assert row["typed"] is False and row["check"] is False and row["undo"] is False

    html = render_children_page("test")
    assert 'id="show-words"' in html and 'id="spoken-words"' in html
    assert re.search(r'id="show-words"[^>]*\bchecked\b', html) is None
    assert "words.checked = Boolean(flags.words && state.showWords)" in script
    assert 'id="pace"' in html

    choose = script.split("function chooseGame()")[1].split("function randomRegion()")[0]
    assert choose.count("armDeadline(") == 2
    assert "applyGameControls()" in choose
    trace = choose.split('state.game==="trace-letter"')[1].split("trace-picture")[0]
    assert "armDeadline(" not in trace

    launch = script.split("function pickLaunchGame()")[1].split("\nfunction ")[0]
    assert 'get("game")' in launch and "Math.random" in launch and "if (requested)" in launch
    assert "trace-letter" not in launch

    css = (ROOT / "src/theodore_children_webcam_lab/static/app.css").read_text()
    assert "body.phone-play #countdown:not(.hidden)" in css
    hidden = css.split("body.phone-play .vision-readout,body.phone-play .vision-status{")[1].split("}")[0]
    assert "countdown" not in hidden
