"""One minimal shell for every Vision Play game, phone-first: real browser, fake camera."""

import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "theodore_children_webcam_lab" / "static"
NODE = shutil.which("node")
PLAYWRIGHT = ROOT.parents[1] / "apps" / "web" / "node_modules" / "playwright"


def test_shell_files_and_removed_chrome_rules():
    page = (ROOT / "src" / "theodore_children_webcam_lab" / "children_page.py").read_text(encoding="utf-8")
    assert "/static/lab_shell.js" in page
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    for needle in ("#lab-progress", "#lab-widget", "#lab-menu", "body.lab-minimal .topbar>:not(#touch-mode){display:none!important}"):
        assert needle in css
    shell = (STATIC / "lab_shell.js").read_text(encoding="utf-8")
    # Double tap is built from pointer events: dblclick is never sent on iOS or in web views.
    assert "pointerdown" in shell and 'addEventListener("dblclick"' not in shell
    game = (STATIC / "pop_quiz_game.js").read_text(encoding="utf-8")
    assert "tapTarget" in game


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(not NODE or not PLAYWRIGHT.exists(), reason="node or playwright is not installed")
def test_every_game_uses_the_minimal_shell_in_a_real_browser():
    port = _free_port()
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT.parents[1] / "packages" / "shared" / "src")]))
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "theodore_children_webcam_lab.main:app", "--port", str(port)],
                              env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                urllib.request.urlopen(url + "/health", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.25)
        result = subprocess.run([NODE, str(ROOT / "tests/minimal_shell_check.mjs")], env=dict(env, LAB_URL=url),
                                check=False, capture_output=True, text=True, timeout=240)
        assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-2500:]
        assert "minimal shell ok" in result.stdout
    finally:
        server.terminate()
        server.wait(timeout=10)
