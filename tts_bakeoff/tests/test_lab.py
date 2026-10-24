"""Launcher, demo generation, license export and panel compatibility for the listening lab."""
from __future__ import annotations

import http.client
import json
from pathlib import Path

import pytest

from tts_bakeoff import panel
from tts_bakeoff.lab import content_type, lab_data, lab_data_js, list_run, parse_range, safe_join, serve_in_thread, export_standalone
from tts_bakeoff.lab.demo import DEMO_LANGS, DEMO_LIMIT, VOICES, make_demo


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory) -> Path:
    return make_demo(tmp_path_factory.mktemp("lab-demo"))


@pytest.fixture()
def server(demo_run):
    srv, _ = serve_in_thread(demo_run, 0)
    yield srv
    srv.shutdown()
    srv.server_close()


def get(srv, path, headers=None, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
    conn.request(method, path, headers=headers or {})
    resp = conn.getresponse()
    body = resp.read()
    return resp, body


def test_demo_run_has_the_real_layout_and_scores(demo_run):
    assert sorted(p.name for p in demo_run.iterdir()) == sorted(VOICES)
    for model in VOICES:
        root = demo_run / model
        assert json.loads((root / "meta.json").read_text())["demo"] is True
        rows = [json.loads(x) for x in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(rows) == len(DEMO_LANGS) * DEMO_LIMIT and all(r["status"] == "ok" for r in rows)
        assert all((demo_run / r["wav"]).is_file() for r in rows)
        scores = [json.loads(x) for x in (root / "scores.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(scores) == len(rows) and "error" in scores[0] and "audio" in scores[0]


def test_demo_voices_differ_so_they_can_be_told_apart(demo_run):
    a = (demo_run / "voxcpm2" / "en" / "S01.wav").read_bytes()
    b = (demo_run / "cosyvoice2" / "en" / "S01.wav").read_bytes()
    assert a != b and len(a) != len(b)


def test_license_export_marks_reference_models_not_shippable():
    cands = {c["adapter"]: c for c in lab_data()["candidates"] if c["adapter"]}
    assert cands["fish_speech15"]["label"] == "NOT SHIPPABLE"
    assert cands["voxcpm2"]["label"] in {"SHIPPABLE", "CHECK LICENSE", "NOT SHIPPABLE"}
    js = lab_data_js("/run/")
    assert js.startswith("window.LAB_DATA = ") and '"base": "/run/"' in js
    sentences = lab_data()["sentences"]
    assert set(sentences) >= {"km", "en"} and sentences["km"][0]["id"] and sentences["km"][0]["text"]


def test_static_files_and_lab_data_are_served(server):
    for path, ctype in [("/", "text/html"), ("/lab.js", "text/javascript"), ("/lab.css", "text/css"), ("/lab_data.js", "text/javascript")]:
        resp, body = get(server, path)
        assert resp.status == 200 and resp.getheader("Content-Type").startswith(ctype) and body
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
    resp, body = get(server, "/api/run")
    listing = json.loads(body)
    assert any(f["path"] == "voxcpm2/en/S01.wav" for f in listing["files"])
    assert any(f["path"].endswith("manifest.jsonl") for f in listing["files"])


def test_audio_is_served_with_correct_mime_and_range_support(server, demo_run):
    full = (demo_run / "voxcpm2" / "en" / "S01.wav").read_bytes()
    resp, body = get(server, "/run/voxcpm2/en/S01.wav")
    assert resp.status == 200 and resp.getheader("Content-Type") == "audio/wav" and resp.getheader("Accept-Ranges") == "bytes" and body == full
    resp, body = get(server, "/run/voxcpm2/en/S01.wav", {"Range": "bytes=0-99"})
    assert resp.status == 206 and body == full[:100] and resp.getheader("Content-Range") == f"bytes 0-99/{len(full)}"
    resp, body = get(server, "/run/voxcpm2/en/S01.wav", {"Range": "bytes=-50"})
    assert resp.status == 206 and body == full[-50:]
    resp, body = get(server, "/run/voxcpm2/en/S01.wav", {"Range": f"bytes={len(full) + 5}-"})
    assert resp.status == 416 and resp.getheader("Content-Range") == f"bytes */{len(full)}"
    resp, body = get(server, "/run/voxcpm2/en/S01.wav", method="HEAD")
    assert resp.status == 200 and body == b"" and int(resp.getheader("Content-Length")) == len(full)
    resp, _ = get(server, "/run/voxcpm2/manifest.jsonl")
    assert resp.getheader("Content-Type") == "application/x-ndjson"


@pytest.mark.parametrize("path", [
    "/run/../../etc/passwd", "/run/%2e%2e/%2e%2e/etc/passwd", "/run/voxcpm2/../../../etc/hosts", "/run//etc/passwd",
    "/run/..%2f..%2fetc/passwd", "/run/voxcpm2%00.wav", "/run/%5c..%5c..%5cwindows",
])
def test_path_traversal_is_rejected(server, path):
    resp, body = get(server, path)
    assert resp.status in (403, 404) and b"root:" not in body


def test_symlink_that_leaves_the_run_folder_is_not_followed(demo_run, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    link = demo_run / "voxcpm2" / "escape.wav"
    link.symlink_to(secret)
    try:
        assert safe_join(demo_run, "voxcpm2/escape.wav") is None
        assert safe_join(demo_run, "voxcpm2/en/S01.wav") is not None
    finally:
        link.unlink()


def test_listing_skips_hidden_files_and_non_audio(demo_run):
    (demo_run / ".secret.wav").write_bytes(b"x")
    (demo_run / "notes.txt").write_text("x")
    paths = {f["path"] for f in list_run(demo_run)["files"]}
    assert ".secret.wav" not in paths and "notes.txt" not in paths
    (demo_run / ".secret.wav").unlink()
    (demo_run / "notes.txt").unlink()


def test_server_binds_loopback_only(server):
    assert server.server_address[0] == "127.0.0.1"


def test_parse_range_edge_cases():
    assert parse_range(None, 100) is None
    assert parse_range("bytes=10-", 100) == (10, 99)
    assert parse_range("bytes=10-1000", 100) == (10, 99)
    assert parse_range("bytes=50-10", 100) == "bad" and parse_range("bytes=-", 100) == "bad" and parse_range("items=1-2", 100) == "bad"
    assert parse_range("bytes=-0", 100) == "bad"


def test_content_types():
    assert content_type("a.wav") == "audio/wav" and content_type("a.mp3") == "audio/mpeg" and content_type("a.m4a") == "audio/mp4"
    assert content_type("a.flac") == "audio/flac" and content_type("a.webm") == "audio/webm" and content_type("a.ogg") == "audio/ogg"
    assert content_type("a.unknownext") == "application/octet-stream"


def test_export_standalone_opens_from_disk(tmp_path):
    dest = export_standalone(tmp_path / "lab")
    names = {p.name for p in dest.iterdir()}
    assert names == {"index.html", "lab.js", "lab.css", "lab_data.js"}
    html = (dest / "index.html").read_text(encoding="utf-8")
    assert 'src="lab_data.js"' in html and "http://" not in html.replace("http://127", "")  # no CDN or remote assets
    js = (dest / "lab.js").read_text(encoding="utf-8")
    assert "fetch('http" not in js and "https://" not in js and "innerHTML" not in js


def test_lab_rating_export_aggregates_with_the_existing_panel_command(tmp_path):
    """A lab export carries its own id:label key, so `panel aggregate` works without a built panel."""
    ratings = {
        "panel": "lab-km-7", "lang": "km", "rater": "tester",
        "ratings": [
            {"id": "S01", "label": "A", "naturalness": 5, "clarity": 4},
            {"id": "S01", "label": "B", "naturalness": 2, "clarity": 3},
        ],
        "key": {"S01:A": "voxcpm2", "S01:B": "cosyvoice2"},
    }
    f = tmp_path / "ratings_lab_km_tester.json"
    f.write_text(json.dumps(ratings), encoding="utf-8")
    rows = panel.aggregate(tmp_path, [f])
    by = {r["model"]: r for r in rows}
    assert by["voxcpm2"]["naturalness"] == 5 and by["cosyvoice2"]["clarity"] == 3
    assert (tmp_path / "panel" / "panel_results.csv").exists()


def test_aggregate_still_rejects_unknown_panels_without_a_key(tmp_path):
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"panel": "nope", "lang": "km", "rater": "x", "ratings": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        panel.aggregate(tmp_path, [f])
