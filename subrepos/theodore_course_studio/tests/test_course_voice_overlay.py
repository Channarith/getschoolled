"""Smoke + parity tests for the Sala-only voice-first overlay.

The overlay ships as a vanilla ES module (``voice_static/course_voice.js``) and
is referenced from ``render_studio_page``. The template itself is 7.5k lines, so
these checks exist to protect against two silent regressions:

* The ``<script>`` tag that pulls the overlay in disappears from the page.
* The intent catalog in the vanilla JS parser drifts away from the TypeScript
  catalog shared with web + mobile (``apps/web/app/lib/courseVoiceIntent.ts``).

The intent list is the single source of truth for *what Sala can do by voice*
in the current player, so every renderer MUST agree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theodore_course_studio.main import app
from theodore_course_studio.studio_page import render_studio_page


_PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "theodore_course_studio"
_VOICE_JS = _PKG_ROOT / "voice_static" / "course_voice.js"
_WEB_INTENT_TS = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "web"
    / "app"
    / "lib"
    / "courseVoiceIntent.ts"
)


def _extract_catalog(text: str) -> list[str]:
    """Pull the quoted strings out of the ``courseVoiceIntentCatalog`` body.

    Finds the ``function courseVoiceIntentCatalog`` definition first, then
    the first ``[`` opened AFTER its opening ``{`` -- that is the returned
    tuple. This skips earlier ``"kind"`` discriminators and the
    ``CourseVoiceIntent["kind"]`` indexed-access type that both appear above
    the function in the TypeScript source.
    """
    # Find "function courseVoiceIntentCatalog" (or "function* ...", etc.) and
    # take everything from the opening '{' of its body onward.
    header = re.search(
        r"function\s+courseVoiceIntentCatalog[^{]*\{",
        text,
        re.DOTALL,
    )
    assert header is not None, "could not find courseVoiceIntentCatalog in source"
    body = text[header.end():]
    bracket = re.search(r"\[([^\]]+)\]", body)
    assert bracket is not None, "catalog array not found inside function body"
    return re.findall(r'"([a-z_]+)"', bracket.group(1))


def test_voice_module_is_included_in_studio_html() -> None:
    """``render_studio_page`` must reference the voice overlay module."""
    html = render_studio_page()
    # The mount lives at /api/studio/voice-overlay (not /voice) so the
    # existing POST /api/studio/voice/status endpoint keeps answering.
    assert "/api/studio/voice-overlay/course_voice.js" in html
    # The feature-flag plumbing on the parent side appends ?typemode=1 when the
    # accessibility flag is on; the overlay reads it from location.search, so
    # the module script tag itself should NOT hard-code typemode on the src.
    script_match = re.search(r'<script[^>]*src="([^"]+course_voice\.js[^"]*)"', html)
    assert script_match is not None, "voice overlay <script> tag missing"
    assert "typemode" not in script_match.group(1)


def test_voice_static_route_serves_the_module() -> None:
    client = TestClient(app)
    response = client.get("/api/studio/voice-overlay/course_voice.js")
    assert response.status_code == 200
    body = response.text
    assert "courseVoiceIntentCatalog" in body
    assert "initCourseVoiceOverlay" in body
    # Regression guard: the overlay mount must NOT shadow the voice agent
    # endpoint that lives on the sibling path.
    status = client.get("/api/studio/voice/status")
    assert status.status_code == 200, status.text


def test_voice_overlay_catalog_matches_web_source() -> None:
    """Both parsers must agree on every intent kind."""
    if not _WEB_INTENT_TS.exists():
        pytest.skip("web intent source not present in this checkout")
    js_catalog = _extract_catalog(_VOICE_JS.read_text(encoding="utf-8"))
    ts_catalog = _extract_catalog(_WEB_INTENT_TS.read_text(encoding="utf-8"))
    assert js_catalog == ts_catalog, (
        "course_voice.js and courseVoiceIntent.ts disagree on intent catalog;\n"
        f"js:  {js_catalog}\nts:  {ts_catalog}"
    )


def test_voice_module_runs_on_url_opt_out() -> None:
    """The boot code must respect ``?voicefirst=0`` for A/B and debugging."""
    js = _VOICE_JS.read_text(encoding="utf-8")
    assert 'params.get("voicefirst") === "0"' in js
    assert 'params.get("typemode") === "1"' in js


def test_voice_overlay_hides_chrome_by_default_via_css() -> None:
    """The chrome-hide CSS class must be present in the rendered page."""
    html = render_studio_page()
    assert "body.aoep-voice-first" in html
    # Fail-safe: the overlay also tags .aoep-voice-revealed when the learner
    # falls back to classic chrome; CSS must hide the pill at that point.
    assert ".sala-pill" in html


def test_demo_mode_is_clean_and_uses_the_logo_avatar():
    html = render_studio_page()
    assert "body.demo-clean #course-price" in html
    assert "sala-gold.png" in html
    assert "sala-giggle.png" in html
    js = _VOICE_JS.read_text(encoding="utf-8")
    assert 'params.get("demo") === "1"' in js
    assert "parseDemoCommand" in js
    assert (_PKG_ROOT / "voice_static" / "salareen-logo.webp").is_file()
    # Demo-only commands must not leak into the catalog shared with web + mobile.
    assert "audio_off" not in _extract_catalog(js)


def test_demo_has_a_tutorial_help_button_and_goes_full_screen_on_phones():
    js = _VOICE_JS.read_text(encoding="utf-8")
    assert "showDemoTutorial" in js and "sala_demo_tutorial_seen_v1" in js
    assert 'clickById("btn-fullscreen")' in js and "orientation" in js
    # Buttons live in the full-screen element, or they would not be drawn in full screen.
    assert "fullscreenElement" in js and "mountOnTop" in js
    html = render_studio_page()
    for selector in (".sala-tutorial", ".sala-help", ".sala-rotate", "body.demo-clean .teach-stage"):
        assert selector in html
    # On phones the slide must not be capped to half the screen in the demo.
    assert "max-height:none !important" in html
