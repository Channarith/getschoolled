"""Every button a game's how-to names (Check, Hear it, Undo, Play, the microphone) must be shown by that game."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "theodore_children_webcam_lab" / "static"
PROMISED = {"check": r"\bCheck\b", "hear": r"\bHear it\b", "undo": r"\bUndo\b", "play": r"\bPlay\b", "mic": r"microphone"}


def controls_table() -> dict[str, dict[str, bool]]:
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    table = {}
    for m in re.finditer(r'"([a-z0-9-]+)":\s*\{([^}]*)\}', app):
        flags = dict(re.findall(r"(\w+):(true|false)", m.group(2)))
        if "play" in flags:
            table[m.group(1)] = {k: v == "true" for k, v in flags.items()}
    return table


def howto_text() -> dict[str, str]:
    js = ('import {HOWTO, howtoFor} from "%s"; const o = {}; for (const id of Object.keys(HOWTO)) '
          'o[id] = howtoFor(id, "en").lines.join(" "); console.log(JSON.stringify(o));' % (STATIC / "game_howto.js").as_posix())
    return json.loads(subprocess.check_output(["node", "--input-type=module", "-e", js], text=True, timeout=60))


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_buttons_named_in_each_how_to_are_shown_by_that_game():
    table, how = controls_table(), howto_text()
    assert len(how) >= 40
    problems = []
    for game, text in how.items():
        flags = table.get(game)
        if flags is None:
            problems.append(f"{game}: no controls entry (a new game gets Play only)")
            continue
        for flag, rx in PROMISED.items():
            if re.search(rx, text) and not flags.get(flag, False):
                problems.append(f"{game}: how-to names '{flag}' but the game does not show it")
    assert not problems, "\n".join(problems)
