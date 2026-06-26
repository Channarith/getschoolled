"""Unit tests for the orchestrator's best-effort memory client.

The client must fail open: disabled (no MEMORY_URL) or unreachable memory returns
neutral signals and no-op writes, so the offline single-service demo keeps working.
"""

import json

from aoep_shared.adaptive import LearnerSignals
from orchestrator.memory_client import MemoryClient


class _FakeResp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._b

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def test_disabled_client_returns_neutral_signals():
    mc = MemoryClient(None)
    assert mc.enabled is False
    # Reads return defaults; writes are silent no-ops that never raise.
    assert mc.learner_signals("stu", "topic") == LearnerSignals()
    assert mc.update_mastery("stu", "topic", True) is None
    mc.record_behavior("stu", "topic", quiz_correct=True)  # no exception


def test_unreachable_memory_degrades_gracefully():
    # Port 1 refuses immediately -> client must swallow it and degrade.
    mc = MemoryClient("http://127.0.0.1:1")
    assert mc.enabled is True
    assert mc.learner_signals("stu", "topic") == LearnerSignals()
    assert mc.update_mastery("stu", "topic", False) is None
    mc.record_behavior("stu", "topic", saw_slide=True)  # no exception


def test_learner_signals_maps_json(monkeypatch):
    mc = MemoryClient("http://memory.test")
    payload = {
        "topic_mastery": 0.9,
        "quiz_accuracy": 0.8,
        "avg_response_latency_s": 3.0,
        "attention_trend": 0.95,
        "question_rate": 0.25,
    }
    monkeypatch.setattr(
        "orchestrator.memory_client.urllib.request.urlopen",
        lambda req, timeout=None: _FakeResp(payload),
    )
    s = mc.learner_signals("stu", "topic")
    assert s.topic_mastery == 0.9
    assert s.quiz_accuracy == 0.8
    assert s.avg_response_latency_s == 3.0
    assert s.attention_trend == 0.95
    assert s.question_rate == 0.25


def test_update_mastery_parses_score(monkeypatch):
    mc = MemoryClient("http://memory.test")
    monkeypatch.setattr(
        "orchestrator.memory_client.urllib.request.urlopen",
        lambda req, timeout=None: _FakeResp({"mastery": 0.73}),
    )
    assert mc.update_mastery("stu", "topic", True) == 0.73
