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
LOOP = {
    "trace-letter": "updateTrace",
    "trace-picture": "updateTrace",
    "say-letter": "checkSpeech",
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
    assert len(catalog) == len(LOOP) == 22

    html = render_children_page("test")
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
            assert 'state.game!=="say-letter"' in script


def test_every_picture_word_has_a_glyph_on_both_sides():
    script = _js()
    assert set(PICTURE_EMOJI) == set(PICTURE_WORDS.values())
    for word, glyph in PICTURE_EMOJI.items():
        assert glyph in script
        assert word in script


def test_pointer_demo_listens_on_the_stage_not_the_dead_canvas():
    script = _js()
    assert 'stage.addEventListener("pointermove",applyDemoPointer)' in script
    assert "syntheticHand" in script
    css = (ROOT / "src/theodore_children_webcam_lab/static/app.css").read_text()
    assert ".stage.demo" in css
    assert ".stage video" in css and "pointer-events:none" in css
