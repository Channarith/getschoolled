from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import orchestrator.teaching as teaching
from aoep_shared.current_awareness import CurrentAwarenessResult, CurrentSource
from orchestrator.main import app
from orchestrator.curriculum import CurriculumStore
from orchestrator.teaching import TeachingSessions


LESSON = "intro-to-photosynthesis"


def _source() -> CurrentSource:
    return CurrentSource(
        title="Official World Cup result",
        url="https://www.fifa.com/tournaments/example",
        publisher="www.fifa.com",
        snippet="Team A won the latest World Cup final.",
        excerpt="The official result says Team A won the latest World Cup final.",
        engine="canned",
        published_at="2026-07-19T20:00:00Z",
        fetched_at="2026-08-22T10:00:00Z",
    )


def _result(*, status: str, sources=None) -> CurrentAwarenessResult:
    return CurrentAwarenessResult(
        query="Who won the latest World Cup?",
        routed=True,
        status=status,
        as_of="2026-08-22T10:00:00Z",
        sources=list(sources or []),
        message="live evidence status",
    )


class FakeLlm:
    text = "The official result says Team A won the latest World Cup final."

    def complete(self, _messages):
        return SimpleNamespace(text=self.text)

    def complete_stream(self, _messages):
        yield self.text


def _sessions() -> tuple[TeachingSessions, str]:
    root = Path(__file__).resolve().parents[3] / "sample-curriculum"
    sessions = TeachingSessions(
        app.state.factory,
        curriculum=CurriculumStore(str(root)),
    )
    sessions.llm = FakeLlm()
    state = sessions.start_session(LESSON, "group")
    return sessions, state.session_id


def test_verified_current_answer_has_linked_sources_and_as_of(monkeypatch):
    monkeypatch.setattr(
        teaching,
        "research_current_topic",
        lambda *_args, **_kwargs: _result(status="verified", sources=[_source()]),
    )
    sessions, session_id = _sessions()
    answer = sessions.ask(session_id, "Who won the latest World Cup?")
    assert answer.grounded is True
    assert answer.as_of == "2026-08-22T10:00:00Z"
    assert answer.sources[0]["url"].startswith("https://www.fifa.com/")
    assert answer.citations == [
        "Official World Cup result — https://www.fifa.com/tournaments/example"
    ]


def test_unverified_current_answer_abstains_instead_of_using_model_memory(monkeypatch):
    monkeypatch.setattr(
        teaching,
        "research_current_topic",
        lambda *_args, **_kwargs: _result(status="unavailable"),
    )
    sessions, session_id = _sessions()
    answer = sessions.ask(session_id, "Who is the current president?")
    assert answer.grounded is False
    assert answer.hallucination_risk == 1.0
    assert "cannot verify a current answer" in answer.text
    assert "will not guess from model memory" in answer.text


def test_streaming_current_answer_includes_structured_sources(monkeypatch):
    monkeypatch.setattr(
        teaching,
        "research_current_topic",
        lambda *_args, **_kwargs: _result(status="verified", sources=[_source()]),
    )
    sessions, session_id = _sessions()
    events = list(
        sessions.ask_stream(session_id, "Who won the latest World Cup?")
    )
    done = events[-1]
    assert done["type"] == "done"
    assert done["as_of"] == "2026-08-22T10:00:00Z"
    assert done["sources"][0]["publisher"] == "www.fifa.com"
