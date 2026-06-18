"""Provenance sign/verify API (Trust layer, Phase 2)."""

from fastapi.testclient import TestClient

from curriculum.main import app

client = TestClient(app)


def test_sign_then_verify():
    signed = client.post("/provenance/sign", json={
        "artifact_id": "scene-1", "content": "photosynthesis lesson",
        "ai_generated": True, "model": "edu-7b", "human_reviewed": True,
        "reviewer": "Dr. Lee", "sources": ["https://oer.org/a"],
    }).json()
    assert signed["signature"]

    res = client.post("/provenance/verify", json={
        "signed": signed, "content": "photosynthesis lesson"
    }).json()
    assert res["valid"] is True
    assert res["content_matches"] is True
    labels = {a["label"] for a in res["assertions"]}
    assert "c2pa.ai_generated" in labels and "aoep.human_reviewed" in labels


def test_verify_detects_changed_content():
    signed = client.post("/provenance/sign", json={
        "artifact_id": "d1", "content": "original text"
    }).json()
    res = client.post("/provenance/verify", json={
        "signed": signed, "content": "tampered text"
    }).json()
    assert res["content_matches"] is False
