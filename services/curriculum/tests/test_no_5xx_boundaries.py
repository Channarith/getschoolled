"""Bad input and missing optional config must not become 5xx responses."""

from __future__ import annotations

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app, raise_server_exceptions=False)
WEIRD = "héllo 你好 ខ្មែរ"


def test_scene_verify_with_non_ascii_signature_is_invalid_not_500():
    scene = {"title": "t", "width": 100, "height": 100, "layers": []}
    r = client.post("/scenes/verify", json={"content_hash": WEIRD, "signature": WEIRD, "scene": scene})
    assert r.status_code == 200
    assert r.json() == {"valid": False}


def test_provenance_verify_with_non_ascii_signature_is_invalid_not_500():
    manifest = {"artifact_id": "a", "content_sha256": "0" * 64, "assertions": []}
    r = client.post("/provenance/verify", json={"signed": {"signature": WEIRD, "manifest": manifest}})
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_scholar_search_without_key_is_an_empty_200(monkeypatch):
    monkeypatch.delenv("RAPIDAPI_KEY", raising=False)
    r = client.get("/scholar/search", params={"q": WEIRD})
    assert r.status_code == 200
    body = r.json()
    assert body["publications"] == [] and body["available"] is False
