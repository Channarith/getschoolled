"""The camera check page (/diag/vision), the triage log, and the model-file handling that phones depend on."""

import mimetypes
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Mount

from theodore_children_webcam_lab.main import VisionStaticFiles, app

LAB = Path(__file__).resolve().parents[1]
PKG = LAB / "src" / "theodore_children_webcam_lab"
STATIC = PKG / "static"


def test_camera_check_page_is_public_and_not_cached():
    res = TestClient(app).get("/diag/vision")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-cache"
    html = res.text
    assert "Camera check" in html
    assert 'name="robots" content="noindex"' in html
    assert "/static/vision_diag_page.js?v=" in html
    assert "Nothing is uploaded" in html
    assert 'id="copy"' in html and 'id="share"' in html


def test_vision_files_keep_a_cache_lifetime_and_get_the_right_types(tmp_path):
    (tmp_path / "wasm").mkdir()
    (tmp_path / "wasm" / "vision_wasm_internal.wasm").write_bytes(b"\0asm\1\0\0\0")
    (tmp_path / "selfie_segmenter.tflite").write_bytes(b"x" * 64)
    (tmp_path / "face_landmarker.task").write_bytes(b"x" * 64)
    mimetypes.add_type("application/octet-stream", ".tflite")
    mimetypes.add_type("application/octet-stream", ".task")
    client = TestClient(Starlette(routes=[Mount("/vendor/vision", VisionStaticFiles(directory=tmp_path))]))
    wasm = client.get("/vendor/vision/wasm/vision_wasm_internal.wasm")
    assert wasm.headers["content-type"] == "application/wasm"
    assert "max-age=86400" in wasm.headers["cache-control"]
    tflite = client.get("/vendor/vision/selfie_segmenter.tflite")
    assert tflite.headers["content-type"] == "application/octet-stream"
    assert "max-age=86400" in tflite.headers["cache-control"]
    assert client.get("/vendor/vision/missing.bin").status_code == 404


def test_new_scripts_are_part_of_the_cache_busting_fingerprint():
    main = (PKG / "main.py").read_text(encoding="utf-8")
    for name in ("vision_diag.js", "vision_diag_page.js", "vision_assets.js"):
        assert f'"{name}"' in main


def test_triage_log_covers_what_a_phone_failure_needs():
    js = (STATIC / "vision_diag.js").read_text(encoding="utf-8")
    for needle in (
        "MAX_ENTRIES = 2000",             # ring buffer size
        "localStorage",                    # survives a crash or reload
        "unhandledrejection",
        "getUserMedia",                    # exact DOMException name and message
        "permissions.query",               # camera and microphone state changes
        "WEBGL_debug_renderer_info",       # GPU renderer
        "hardwareConcurrency",
        "deviceMemory",
        "crossOriginIsolated",
        "SharedArrayBuffer",
        "loadedmetadata",                  # video element events
        "ReactNativeWebView",              # batches go to the app
        "salareen-diag",
        "eyJ",                             # token redaction
    ):
        assert needle in js, needle
    # No image or audio capture of any kind.
    for forbidden in ("toDataURL", "captureStream", "MediaRecorder", "getImageData"):
        assert forbidden not in js, forbidden


def test_model_files_are_stored_once_and_fall_back_to_plain_urls():
    assets = (STATIC / "vision_assets.js").read_text(encoding="utf-8")
    assert "caches.open" in assets and "indexedDB" in assets
    assert "vision_wasm_nosimd_internal" in assets and "vision_wasm_internal" in assets
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "modelAssetBuffer" in app_js and "modelAssetPath: path" in app_js     # buffer when stored, URL otherwise
    assert "loadVisionAssets" in app_js
    # Never fatal: a failed storage step is noted and the old URL path is used.
    assert 'note("asset cache", error)' in app_js


def test_low_memory_phones_skip_the_optional_body_outline():
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "navigator.deviceMemory" in app_js and "off (low memory)" in app_js


def test_detection_loop_reports_per_frame_stats_to_the_log():
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "trace.frame(sample)" in app_js
    assert "trace.expose(" in app_js
    assert "import {diag as trace} from" in app_js   # the page has its own local `diag`; the import must not shadow it


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("name", ["vision_diag.js", "vision_diag_page.js", "vision_assets.js", "app.js"])
def test_scripts_parse(name):
    result = subprocess.run(["node", "--check", str(STATIC / name)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
