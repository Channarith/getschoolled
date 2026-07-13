"""Streaming conversational agent: POST /api/sessions/{id}/ask/stream (SSE)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

import orchestrator.main as main
from orchestrator.main import app

client = TestClient(app)


def _first_lesson() -> str:
    return client.get("/api/lessons").json()[0]["lesson_id"]


def _start() -> str:
    r = client.post("/api/sessions", json={"lesson_id": _first_lesson(), "class_type": "solo"})
    return r.json()["session"]["session_id"]


def _parse_sse(text: str):
    return [json.loads(line[len("data:"):].strip())
            for line in text.splitlines() if line.startswith("data:")]


def test_ask_stream_unknown_session_404():
    r = client.post("/api/sessions/nope/ask/stream", json={"text": "hi"})
    assert r.status_code == 404


def test_ask_stream_offline_fallback_streams_then_done():
    """With no reachable LLM, the agent streams the grounded offline answer then a
    final 'done' event with citations + grounding metadata."""
    sid = _start()
    r = client.post(f"/api/sessions/{sid}/ask/stream", json={"text": "what is this about?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(r.text)
    assert events, "expected SSE events"
    assert events[-1]["type"] == "done"
    assert "text" in events[-1] and events[-1]["text"].strip()
    assert isinstance(events[-1]["citations"], list)
    assert "grounded" in events[-1]


def test_ask_stream_uses_llm_deltas(monkeypatch):
    """When the agent's LLM streams tokens, they arrive as incremental deltas."""
    sid = _start()
    sessions = main.get_sessions()

    class FakeLLM:
        def complete_stream(self, messages, **kw):
            for t in ["Photo", "synthesis ", "is grounded."]:
                yield t

        def complete(self, messages, **kw):  # pragma: no cover - not used here
            from aoep_shared.providers.base import Completion
            return Completion(text="x", model="fake")

    monkeypatch.setattr(sessions, "llm", FakeLLM())
    r = client.post(f"/api/sessions/{sid}/ask/stream", json={"text": "explain photosynthesis"})
    events = _parse_sse(r.text)
    deltas = [e["text"] for e in events if e["type"] == "delta"]
    assert "Photo" in deltas   # streamed incrementally
    assert any(e["type"] == "done" for e in events)
