"""Shared session store: backends, env factory, and multi-replica behaviour.

The point of the store is that orchestrator replicas share live-class session
state, so a follow-up advance/ask served by a different pod still finds the
session. These tests simulate "different pods" as separate ``TeachingSessions``
instances that share (or don't share) a store.
"""

from __future__ import annotations

import pytest

from orchestrator.main import app
from orchestrator.sessions import (
    InMemorySessionStore,
    RedisSessionStore,
    build_session_store,
)
from orchestrator.teaching import SessionState, TeachingSessions

LESSON = "intro-to-photosynthesis"


class FakeRedis:
    """Minimal Redis stand-in (decode_responses=True semantics: str values)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    def delete(self, key):
        self.store.pop(key, None)
        self.ttls.pop(key, None)


def _factory():
    return app.state.factory


# --------------------------------------------------------------------------- #
# Backend unit tests
# --------------------------------------------------------------------------- #
def test_in_memory_store_roundtrip():
    store = InMemorySessionStore()
    s = SessionState(session_id="abc123", class_type="group", lesson_id=LESSON)
    assert store.get("abc123") is None
    store.save(s)
    got = store.get("abc123")
    assert got is not None and got.lesson_id == LESSON
    store.delete("abc123")
    assert store.get("abc123") is None


def test_redis_store_serializes_and_sets_ttl():
    r = FakeRedis()
    store = RedisSessionStore(r, SessionState, ttl_seconds=123)
    s = SessionState(session_id="zz", class_type="solo", lesson_id=LESSON, current_slide=2)
    store.save(s)
    # Stored as JSON under the prefixed key, with the TTL applied.
    assert "aoep:sess:zz" in r.store
    assert r.ttls["aoep:sess:zz"] == 123
    got = store.get("zz")
    assert isinstance(got, SessionState)
    assert got.current_slide == 2 and got.lesson_id == LESSON
    store.delete("zz")
    assert store.get("zz") is None


def test_redis_store_get_falls_back_when_redis_errors():
    class BrokenRedis(FakeRedis):
        def get(self, key):
            raise RuntimeError("connection refused")

    store = RedisSessionStore(BrokenRedis(), SessionState)
    # No exception bubbles up; missing key -> None via the in-memory fallback.
    assert store.get("missing") is None


# --------------------------------------------------------------------------- #
# Factory (env-driven selection)
# --------------------------------------------------------------------------- #
def test_factory_defaults_to_memory(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("SESSION_BACKEND", raising=False)
    assert build_session_store(SessionState).name == "memory"


def test_factory_memory_override_beats_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SESSION_BACKEND", "memory")
    assert build_session_store(SessionState).name == "memory"


# --------------------------------------------------------------------------- #
# Multi-replica behaviour (the actual bug + fix)
# --------------------------------------------------------------------------- #
def test_shared_store_lets_a_second_pod_serve_the_session():
    """Pod A starts the session; pod B (same shared store) can advance + ask."""
    shared = RedisSessionStore(FakeRedis(), SessionState)
    pod_a = TeachingSessions(_factory(), store=shared)
    pod_b = TeachingSessions(_factory(), store=shared)

    state = pod_a.start_session(LESSON, "group")
    sid = state.session_id

    # B finds the session A created (would 404 without a shared store).
    slide = pod_b.advance(sid)
    assert slide.index == 1
    answer = pod_b.ask(sid, "What gas do plants release?")
    assert answer.text

    # The advance + ask mutations B made are visible back on A.
    assert pod_a.get_session(sid).current_slide == 1
    assert len(pod_a.get_session(sid).history) == 2


def test_separate_in_memory_stores_reproduce_the_404():
    """Without a shared store, a second pod doesn't know the session (the bug)."""
    pod_a = TeachingSessions(_factory(), store=InMemorySessionStore())
    pod_b = TeachingSessions(_factory(), store=InMemorySessionStore())

    sid = pod_a.start_session(LESSON, "group").session_id
    with pytest.raises(KeyError):
        pod_b.advance(sid)
