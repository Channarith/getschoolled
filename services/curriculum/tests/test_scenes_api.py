"""AOEPLX scene API tests (curriculum service)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def _make_scene():
    return client.post(
        "/scenes",
        json={
            "title": "Cells",
            "layers": [
                {"id": "vid", "type": "video", "z": 0, "asset_key": "s3://v.mp4"},
                {
                    "id": "draw",
                    "type": "whiteboard",
                    "z": 1,
                    "transform": {"x": 0.3, "y": 0.3, "w": 0.3, "h": 0.3},
                    "time": {"start": 5, "end": 10},
                },
            ],
        },
    ).json()


def test_create_get_scene():
    scene = _make_scene()
    sid = scene["id"]
    assert scene["format"] == "aoeplx"
    got = client.get(f"/scenes/{sid}")
    assert got.status_code == 200
    assert len(got.json()["layers"]) == 2


def test_delta_append_stroke_and_add_layer():
    sid = _make_scene()["id"]
    r = client.post(
        f"/scenes/{sid}/delta",
        json={"op": "append_stroke", "layer_id": "draw",
              "stroke": {"points": [[0.31, 0.31], [0.4, 0.4]]}},
    )
    assert r.status_code == 200, r.text
    draw = next(ly for ly in r.json()["layers"] if ly["id"] == "draw")
    assert len(draw["strokes"]) == 1

    r2 = client.post(
        f"/scenes/{sid}/delta",
        json={"op": "add_layer",
              "layer": {"id": "note1", "type": "note", "anchor_to": "draw",
                        "text": "the nucleus"}},
    )
    assert any(ly["id"] == "note1" for ly in r2.json()["layers"])


def test_extract_region_creates_object():
    sid = _make_scene()["id"]
    r = client.post(
        f"/scenes/{sid}/extract",
        json={"layer_ids": ["draw"], "time": {"start": 7, "end": 7}, "title": "snip"},
    )
    assert r.status_code == 200, r.text
    obj = r.json()
    assert obj["kind"] == "image"
    assert obj["source_scene_id"] == sid
    # Extracted object is retrievable as its own scene.
    assert client.get(f"/scenes/{obj['scene']['id']}").status_code == 200


def test_sign_and_verify_roundtrip_and_tamper():
    sid = _make_scene()["id"]
    signed = client.post(f"/scenes/{sid}/sign").json()
    assert client.post("/scenes/verify", json=signed).json()["valid"] is True
    # Tamper -> invalid.
    signed["scene"]["title"] = "HACKED"
    assert client.post("/scenes/verify", json=signed).json()["valid"] is False


def test_unknown_scene_404():
    assert client.get("/scenes/nope").status_code == 404
