"""Homework endpoints must be locked to internal callers (the AI
teacher agent), NOT exposed to student clients."""

from __future__ import annotations

import os

import pytest
from curriculum.main import app
from fastapi.testclient import TestClient

from aoep_shared.auth import sign_token


HOMEWORK_GET_ROUTES = [
    ("GET", "/homework/grade-reviews"),
]

HOMEWORK_POST_ROUTES = [
    ("POST", "/homework/grade", {"assignment": {"title": "t", "items": []},
                                 "answers": [], "submission_text": ""}),
    ("POST", "/homework/authorship", {"text": "hi"}),
    ("POST", "/homework/generate", {"deck_id": None, "course_id": None,
                                    "topic": "fractions"}),
    ("POST", "/homework/grade-reviews/non-existent/decision",
     {"action": "approve"}),
]


@pytest.fixture(autouse=True)
def _no_disable(monkeypatch):
    """Override the suite-wide RATE_LIMIT_DISABLED conftest leak; we
    explicitly want the internal-auth gate active for these tests."""
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)


def test_homework_get_denied_without_internal_token():
    client = TestClient(app)
    for method, path in HOMEWORK_GET_ROUTES:
        r = client.request(method, path)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
        assert "internal" in r.json()["detail"].lower()


def test_homework_post_denied_without_internal_token():
    client = TestClient(app)
    for method, path, body in HOMEWORK_POST_ROUTES:
        r = client.request(method, path, json=body)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code} {r.text}"


def test_homework_denied_with_wrong_token():
    os.environ["INTERNAL_TOKEN"] = "the-real-token"
    try:
        client = TestClient(app)
        r = client.post("/homework/authorship",
                        json={"text": "hi"},
                        headers={"X-Internal-Token": "guessed"})
        assert r.status_code == 403
    finally:
        os.environ.pop("INTERNAL_TOKEN", None)


def test_homework_allowed_with_static_token():
    os.environ["INTERNAL_TOKEN"] = "the-real-token"
    try:
        client = TestClient(app)
        r = client.post("/homework/authorship",
                        json={"text": "Photosynthesis makes oxygen."},
                        headers={"X-Internal-Token": "the-real-token"})
        assert r.status_code == 200
        body = r.json()
        assert body["label"] in ("ai", "human", "uncertain")
    finally:
        os.environ.pop("INTERNAL_TOKEN", None)


def test_homework_allowed_with_signed_agent_token():
    os.environ["INTERNAL_TOKEN_KEY"] = "platform-secret-key"
    try:
        tok = sign_token({"sub": "orchestrator-pod-1", "scope": "agent"},
                         b"platform-secret-key", ttl_s=60)
        client = TestClient(app)
        r = client.post("/homework/authorship",
                        json={"text": "Hello"},
                        headers={"X-Internal-Token": tok})
        assert r.status_code == 200
    finally:
        os.environ.pop("INTERNAL_TOKEN_KEY", None)


def test_homework_signed_token_with_user_scope_denied():
    os.environ["INTERNAL_TOKEN_KEY"] = "platform-secret-key"
    try:
        tok = sign_token({"sub": "student-7", "scope": "user"},
                         b"platform-secret-key", ttl_s=60)
        client = TestClient(app)
        r = client.post("/homework/authorship",
                        json={"text": "Hello"},
                        headers={"X-Internal-Token": tok})
        # Student-scope token must not bypass the teacher gate.
        assert r.status_code == 403
    finally:
        os.environ.pop("INTERNAL_TOKEN_KEY", None)


def test_homework_via_bearer_authorization_header():
    """Allow Authorization: Bearer <token> as an alternative to
    X-Internal-Token, matching the orchestrator -> curriculum SDK."""
    os.environ["INTERNAL_TOKEN"] = "the-real-token"
    try:
        client = TestClient(app)
        r = client.post("/homework/authorship",
                        json={"text": "Hello"},
                        headers={"Authorization": "Bearer the-real-token"})
        assert r.status_code == 200
    finally:
        os.environ.pop("INTERNAL_TOKEN", None)
