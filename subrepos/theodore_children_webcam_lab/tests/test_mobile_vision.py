"""Guards for the phone camera path: the voice widget must not cover Start, vision assets are
self-hosted with a CDN fallback, and failures are visible instead of silent."""

from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
STATIC = LAB / "src" / "theodore_children_webcam_lab" / "static"
SHARED_STATIC = LAB.parents[1] / "packages" / "shared" / "src" / "aoep_shared" / "static"


def test_voice_widget_is_a_small_button_on_phones():
    js = (SHARED_STATIC / "lab_live_audio.js").read_text(encoding="utf-8")
    assert "@media (max-width:700px)" in js
    assert ":host(:not(.voice-open)) .box{display:none !important}" in js
    # Opening it adds voice-open, closing removes it again.
    assert 'host.classList.add("voice-open")' in js
    assert 'host.classList.remove("voice-open")' in js


def test_vision_prefers_this_site_then_the_cdn():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "return selfHosted ? [local, cdn] : [cdn];" in js
    assert '"/vendor/vision/tasks-vision.mjs"' in js
    # no silent swallowing: every failure is recorded for the self-check
    assert "state.visionDiag" in js
    assert "openVisionCheck(true)" in js


def test_camera_request_retries_without_hints_and_tells_the_user_to_allow():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "getUserMedia({video:true, audio:false})" in js
    assert "tap Allow" in js


def test_setup_screen_has_the_camera_check_and_a_reachable_start_button():
    page = (LAB / "src" / "theodore_children_webcam_lab" / "children_page.py").read_text(encoding="utf-8")
    assert 'id="vision-check-open"' in page
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "#setup #start{position:sticky" in css


def test_image_bundles_the_vision_library_and_models():
    dockerfile = (LAB / "Dockerfile").read_text(encoding="utf-8")
    assert "AOEP_VISION_ASSET_DIR=/app/vision" in dockerfile
    for name in ("tasks-vision.mjs", "face_landmarker.task", "hand_landmarker.task", "selfie_segmenter.tflite"):
        assert name in dockerfile


def test_quiet_redesign_uses_golden_sala_and_gold_outlines():
    page = (LAB / "src" / "theodore_children_webcam_lab" / "children_page.py").read_text(encoding="utf-8")
    assert "sala-hero.png" in page
    assert (STATIC / "sala-hero.png").stat().st_size > 10_000
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'shadowColor="rgba(246,200,80,.85)"' in js


def test_small_sala_is_a_cutout_not_a_white_box():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "url(/static/sala-hero.png)" in css and "sala-giggle-hero.png" in css
    for name in ("sala-hero.png", "sala-giggle-hero.png"):
        assert (STATIC / name).stat().st_size > 10_000


def test_quiet_v4_gold_body_outline_and_star():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    page = (LAB / "src" / "theodore_children_webcam_lab" / "children_page.py").read_text(encoding="utf-8")
    assert "ImageSegmenter.createFromOptions" in js and "selfie_segmenter.tflite" in js
    assert "function drawBodyOutline" in js and "drawBodyOutline(w,h);" in js and "function drawStar" in js
    assert 'id="show-outline"' in page
    assert "OUTLINE.avgMs > 90" in js  # gives up on a slow phone instead of stuttering
