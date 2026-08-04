"""Tests for the vision_agent FastAPI service endpoints.

Uses FastAPI TestClient (httpx under the hood).  No OpenCV or xAI key needed —
the frame endpoint degrades gracefully when face models are unavailable and
the voice endpoints return clear messages when XAI_API_KEY is absent.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from vision_agent.main import app, _sessions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_sessions():
    """Ensure a clean session store for each test."""
    _sessions.clear()
    yield
    _sessions.clear()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _create_solo_session(client, lesson="Algebra Basics") -> dict:
    resp = client.post("/sessions", json={
        "class_type": "solo",
        "student_ids": ["s-001"],
        "lesson_title": lesson,
    })
    assert resp.status_code == 201
    return resp.json()


def _create_group_session(client) -> dict:
    resp = client.post("/sessions", json={
        "class_type": "group",
        "student_ids": ["s-001", "s-002", "s-003"],
        "lesson_title": "Group Physics",
    })
    assert resp.status_code == 201
    return resp.json()


def _tiny_jpeg() -> bytes:
    """Minimal 1x1 red JPEG for frame upload tests."""
    try:
        import numpy as np
        import cv2
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        img[:, :] = (0, 0, 200)
        ok, buf = cv2.imencode(".jpg", img)
        return buf.tobytes()
    except ImportError:
        # Minimal JPEG magic bytes (won't decode cleanly; detector returns absent).
        return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def test_create_solo_session(client):
    data = _create_solo_session(client)
    assert data["class_type"] == "solo"
    assert "s-001" in data["student_ids"]
    assert data["ended"] is False
    assert "session_id" in data


def test_create_group_session(client):
    data = _create_group_session(client)
    assert data["class_type"] == "group"
    assert len(data["student_ids"]) == 3


def test_invalid_class_type_rejected(client):
    resp = client.post("/sessions", json={"class_type": "webinar"})
    assert resp.status_code == 422


def test_get_session(client):
    created = _create_solo_session(client)
    sid = created["session_id"]
    resp = client.get(f"/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid


def test_get_missing_session(client):
    resp = client.get("/sessions/does-not-exist")
    assert resp.status_code == 404


def test_end_session(client):
    created = _create_solo_session(client)
    sid = created["session_id"]
    resp = client.delete(f"/sessions/{sid}")
    assert resp.status_code == 200
    assert resp.json()["ended"] is True


def test_end_session_blocks_further_access(client):
    created = _create_solo_session(client)
    sid = created["session_id"]
    client.delete(f"/sessions/{sid}")
    # GET after end should 404 (session is ended).
    resp = client.get(f"/sessions/{sid}")
    assert resp.status_code == 404


def test_max_sessions_soft_cap(client, monkeypatch):
    from vision_agent import main as va_main
    monkeypatch.setattr(app.state.config, "vision_agent_max_sessions", 2)
    _create_solo_session(client)
    _create_solo_session(client)
    resp = client.post("/sessions", json={"class_type": "solo"})
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Frame processing
# ---------------------------------------------------------------------------

def test_process_frame_returns_analysis(client):
    sid = _create_solo_session(client)["session_id"]
    frame = _tiny_jpeg()
    resp = client.post(
        f"/sessions/{sid}/frame",
        files={"file": ("frame.jpg", io.BytesIO(frame), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "presence_state" in data
    assert "silhouette_present" in data
    assert "engagement_fraction" in data
    assert data["session_id"] == sid
    assert 0.0 <= data["silhouette_confidence"] <= 1.0


def test_process_frame_invalid_bytes(client):
    sid = _create_solo_session(client)["session_id"]
    resp = client.post(
        f"/sessions/{sid}/frame",
        files={"file": ("frame.jpg", io.BytesIO(b"garbage"), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should not silhouette_present on garbage bytes.
    assert data["silhouette_present"] is False


def test_process_frame_missing_session(client):
    frame = _tiny_jpeg()
    resp = client.post(
        "/sessions/bad-id/frame",
        files={"file": ("f.jpg", io.BytesIO(frame), "image/jpeg")},
    )
    assert resp.status_code == 404


def test_metrics_after_frames(client):
    sid = _create_solo_session(client)["session_id"]
    frame = _tiny_jpeg()
    for _ in range(5):
        client.post(
            f"/sessions/{sid}/frame",
            files={"file": ("frame.jpg", io.BytesIO(frame), "image/jpeg")},
        )
    resp = client.get(f"/sessions/{sid}/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_frames"] == 5
    assert 0.0 <= data["engagement_fraction"] <= 1.0


# ---------------------------------------------------------------------------
# Voice interaction (no XAI key -> graceful degradation)
# ---------------------------------------------------------------------------

def test_voice_query_no_key_returns_503_message(client):
    sid = _create_solo_session(client)["session_id"]
    resp = client.post(f"/sessions/{sid}/voice", json={"text": "What is DNA?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["xai_available"] is False
    assert "XAI_API_KEY" in data["text"] or "not configured" in data["text"]


def test_voice_query_with_mock_key(client, monkeypatch):
    """Test voice endpoint with a mocked xAI key and mocked HTTP."""
    from aoep_shared import xai_voice
    monkeypatch.setattr(
        app.state.config, "xai_api_key", "xai-fake"
    )
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: {
        "choices": [{"message": {"content": "DNA is a double helix!"}}],
        "model": "grok-2-1212",
        "usage": {"prompt_tokens": 5, "completion_tokens": 10},
    })
    sid = _create_solo_session(client)["session_id"]
    resp = client.post(f"/sessions/{sid}/voice", json={"text": "What is DNA?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["xai_available"] is True
    assert "double helix" in data["text"]


def test_frame_chat_no_key_returns_degraded(client):
    sid = _create_solo_session(client)["session_id"]
    frame = _tiny_jpeg()
    resp = client.post(
        f"/sessions/{sid}/frame-chat",
        files={"file": ("frame.jpg", io.BytesIO(frame), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["xai_available"] is False


def test_frame_chat_with_mock_key(client, monkeypatch):
    from aoep_shared import xai_voice
    monkeypatch.setattr(app.state.config, "xai_api_key", "xai-fake")
    monkeypatch.setattr(xai_voice, "_http_post", lambda *a, **kw: {
        "choices": [{"message": {"content": "Student looks engaged and attentive."}}],
        "model": "grok-2-vision-1212",
        "usage": {"prompt_tokens": 50, "completion_tokens": 10},
    })
    sid = _create_solo_session(client)["session_id"]
    frame = _tiny_jpeg()
    resp = client.post(
        f"/sessions/{sid}/frame-chat",
        files={"file": ("frame.jpg", io.BytesIO(frame), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["xai_available"] is True
    assert "engaged" in data["text"]


# ---------------------------------------------------------------------------
# Capabilities endpoint
# ---------------------------------------------------------------------------

def test_capabilities_endpoint(client):
    resp = client.get("/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "silhouette_detection" in data
    assert "face_recognition" in data
    assert "xai_voice_agent" in data
    # No key in test environment.
    assert data["xai_voice_agent"] is False


# ---------------------------------------------------------------------------
# Health / version
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_version(client):
    resp = client.get("/version")
    assert resp.status_code == 200
