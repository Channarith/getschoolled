"""End-to-end test of the per-student live teaching loop.

Proves the wired loop: graded quiz outcomes update mastery in the memory service,
and the *next* quiz for that student adapts its difficulty. Uses an in-process
``FakeMemory`` that mirrors the real ``MemoryStore`` (BKT mastery +
``signals_from_events`` aggregation) so no second service is needed. Solo class
type is used so a high skill is not capped at MEDIUM (see adaptive.py group cap).
"""

import pytest
from aoep_shared.adaptive import LearnerSignals, signals_from_events
from aoep_shared.knowledge import BayesianKnowledgeTracing
from fastapi.testclient import TestClient

from orchestrator.main import app, get_sessions

client = TestClient(app)

PASSAGES = [
    "Photosynthesis: plants convert light into chemical energy stored in sugars.",
    "Chlorophyll: the green pigment that absorbs light for photosynthesis.",
    "Oxygen: a byproduct of photosynthesis released into the air.",
]


class FakeMemory:
    """In-process stand-in for MemoryClient that mirrors the memory service's
    MemoryStore logic (BKT mastery + behavior aggregation)."""

    def __init__(self) -> None:
        self._bkt = BayesianKnowledgeTracing()
        self.mastery: dict = {}
        self.outcomes: dict = {}
        self.latencies: dict = {}
        self.attention: dict = {}
        self.questions: dict = {}
        self.slides: dict = {}

    def record_behavior(self, student_id, topic, *, quiz_correct=None,
                        response_latency_s=None, attention=None,
                        asked_question=False, saw_slide=False) -> None:
        key = (student_id, topic)
        if quiz_correct is not None:
            self.outcomes.setdefault(key, []).append(quiz_correct)
        if response_latency_s is not None:
            self.latencies.setdefault(key, []).append(response_latency_s)
        if attention is not None:
            self.attention.setdefault(key, []).append(attention)
        if asked_question:
            self.questions[key] = self.questions.get(key, 0) + 1
        if saw_slide:
            self.slides[key] = self.slides.get(key, 0) + 1

    def update_mastery(self, student_id, topic, correct):
        key = (student_id, topic)
        prior = self.mastery.get(key, self._bkt.params.p_init)
        updated = self._bkt.update(prior, correct)
        self.mastery[key] = updated
        return updated

    def learner_signals(self, student_id, topic) -> LearnerSignals:
        key = (student_id, topic)
        return signals_from_events(
            quiz_outcomes=self.outcomes.get(key, []),
            response_latencies_s=self.latencies.get(key, []),
            attention_samples=self.attention.get(key, []),
            questions_asked=self.questions.get(key, 0),
            slides_seen=max(1, self.slides.get(key, 0)),
            topic_mastery=self.mastery.get(key, 0.5),
        )


@pytest.fixture
def fake_memory():
    sessions = get_sessions()
    original = sessions.memory
    fake = FakeMemory()
    sessions.memory = fake
    try:
        yield fake
    finally:
        sessions.memory = original


def _quiz_difficulty(topic: str, student: str) -> str:
    r = client.post("/assessment/quiz", json={
        "topic": topic, "passages": PASSAGES,
        "student_id": student, "class_type": "solo",
    })
    assert r.status_code == 200, r.text
    return r.json()["items"][0]["difficulty"]


def _grade(topic: str, student: str, *, correct: bool) -> None:
    # options/answer_index are nominal; only correctness + topic + student matter
    # for the loop. chosen != answer => wrong.
    chosen = 0 if correct else 1
    r = client.post("/assessment/grade", json={
        "item_id": "x", "options": ["a", "b"], "answer_index": 0,
        "chosen_index": chosen, "difficulty": "medium",
        "topic": topic, "student_id": student,
    })
    assert r.status_code == 200, r.text
    assert r.json()["correct"] is correct


def test_quiz_difficulty_rises_as_student_masters_topic(fake_memory):
    topic, student = "photosynthesis", "stu-strong"
    # Cold start: neutral signals -> MEDIUM baseline.
    assert _quiz_difficulty(topic, student) == "medium"
    # A run of correct answers raises mastery + accuracy.
    for _ in range(3):
        _grade(topic, student, correct=True)
    # The loop is closed: the next quiz escalates difficulty.
    assert _quiz_difficulty(topic, student) == "hard"


def test_quiz_difficulty_falls_when_student_struggles(fake_memory):
    topic, student = "fractions", "stu-weak"
    for _ in range(3):
        _grade(topic, student, correct=False)
    assert _quiz_difficulty(topic, student) == "easy"


def test_anonymous_quiz_stays_medium(fake_memory):
    # No student_id -> memory is never consulted; behavior unchanged from before.
    r = client.post("/assessment/quiz", json={
        "topic": "photosynthesis", "passages": PASSAGES,
    })
    assert r.status_code == 200
    assert r.json()["items"][0]["difficulty"] == "medium"


def test_director_and_counters_persist_across_ticks(fake_memory):
    start = client.post("/api/sessions", json={
        "lesson_id": "intro-to-photosynthesis", "class_type": "solo",
        "student_id": "stu-x",
    })
    assert start.status_code == 200, start.text
    sid = start.json()["session"]["session_id"]

    sessions = get_sessions()
    director_first = sessions.director_for(sid)
    client.post(f"/api/sessions/{sid}/advance")
    client.post(f"/api/sessions/{sid}/advance")
    director_again = sessions.director_for(sid)

    # Same persistent Director instance across requests; counters accumulate.
    assert director_first is director_again
    assert sessions.counters_for(sid).slides_seen == 2
