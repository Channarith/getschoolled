"""In-memory profile / consent / mastery store (phase0).

Persistence is Postgres + pgvector in real deployments (see db/migrations); this
process-local store keeps the API shape and the policy logic testable offline.
The mastery score uses a simple exponential moving average over quiz outcomes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from aoep_shared.adaptive import LearnerSignals, signals_from_events
from aoep_shared.knowledge import BayesianKnowledgeTracing
from aoep_shared.schemas import ConsentRecord, ConsentScope

_BKT = BayesianKnowledgeTracing()

# BUG 16 FIX: cap per-topic behavior lists to prevent unbounded growth.
_MAX_BEHAVIOR_EVENTS = 1000


@dataclass
class TopicBehavior:
    """Learning-behavior events for one student on one topic (phase 4)."""

    quiz_outcomes: list[bool] = field(default_factory=list)
    response_latencies_s: list[float] = field(default_factory=list)
    attention_samples: list[float] = field(default_factory=list)
    questions_asked: int = 0
    slides_seen: int = 0


@dataclass
class StudentMemory:
    student_id: str
    display_name: str
    # topic -> mastery in [0, 1]
    mastery: dict[str, float] = field(default_factory=dict)
    # scope -> granted?
    consents: dict[ConsentScope, bool] = field(default_factory=dict)
    # topic -> behavior events
    behavior: dict[str, TopicBehavior] = field(default_factory=dict)


class MemoryStore:
    def __init__(self) -> None:
        self._students: dict[str, StudentMemory] = {}
        self._consent_log: list[ConsentRecord] = []
        # BUG 11 FIX: single lock guards all mutable state to eliminate races
        # between upsert_student, record_consent, record_behavior, and
        # purge_expired (BUGs 11-15).
        self._lock = threading.Lock()

    # ---------------------------------------------------------------------- #
    # Internal helpers — must be called with self._lock already held.
    # ---------------------------------------------------------------------- #

    def _upsert_student_locked(self, student_id: str, display_name: str) -> StudentMemory:
        """BUG 12 FIX: atomic check-then-set under the store lock."""
        mem = self._students.get(student_id)
        if mem is None:
            mem = StudentMemory(student_id=student_id, display_name=display_name)
            self._students[student_id] = mem
        else:
            mem.display_name = display_name
        return mem

    # ---------------------------------------------------------------------- #
    # Public API
    # ---------------------------------------------------------------------- #

    def upsert_student(self, student_id: str, display_name: str) -> StudentMemory:
        with self._lock:
            return self._upsert_student_locked(student_id, display_name)

    def get(self, student_id: str) -> StudentMemory | None:
        return self._students.get(student_id)

    def record_consent(self, record: ConsentRecord) -> None:
        # BUG 13 FIX: hold the lock for the entire append + student lookup so
        # a concurrent purge_expired cannot observe a partially-updated state.
        with self._lock:
            self._consent_log.append(record)
            mem = self._students.get(record.student_id)
            if mem is None:
                mem = self._upsert_student_locked(record.student_id, record.student_id)
            mem.consents[record.scope] = record.granted

    def has_consent(self, student_id: str, scope: ConsentScope) -> bool:
        mem = self._students.get(student_id)
        return bool(mem and mem.consents.get(scope, False))

    def update_mastery(
        self, student_id: str, topic: str, correct: bool, *, alpha: float = 0.4
    ) -> float:
        """Update P(known) for a topic via Bayesian Knowledge Tracing (phase 4).

        (`alpha` is accepted for backwards compatibility but no longer used; the
        BKT learn/slip/guess/forget model supersedes the old EMA.)
        """
        with self._lock:
            mem = self._students.get(student_id)
            if mem is None:
                mem = self._upsert_student_locked(student_id, student_id)
            prior = mem.mastery.get(topic, _BKT.params.p_init)
            updated = _BKT.update(prior, correct)
            mem.mastery[topic] = updated
        return updated

    def record_behavior(
        self,
        student_id: str,
        topic: str,
        *,
        quiz_correct: bool | None = None,
        response_latency_s: float | None = None,
        attention: float | None = None,
        asked_question: bool = False,
        saw_slide: bool = False,
    ) -> None:
        """Record raw learning-behavior events that feed the adaptive policy."""
        # BUG 14 FIX: hold the lock for the student lookup + behavior update so
        # a concurrent upsert_student / purge_expired cannot create a split view.
        with self._lock:
            mem = self._students.get(student_id)
            if mem is None:
                mem = self._upsert_student_locked(student_id, student_id)
            beh = mem.behavior.setdefault(topic, TopicBehavior())
            # BUG 16 FIX: cap each list at _MAX_BEHAVIOR_EVENTS entries.
            if quiz_correct is not None:
                beh.quiz_outcomes.append(quiz_correct)
                if len(beh.quiz_outcomes) > _MAX_BEHAVIOR_EVENTS:
                    beh.quiz_outcomes = beh.quiz_outcomes[-_MAX_BEHAVIOR_EVENTS:]
            if response_latency_s is not None:
                beh.response_latencies_s.append(response_latency_s)
                if len(beh.response_latencies_s) > _MAX_BEHAVIOR_EVENTS:
                    beh.response_latencies_s = beh.response_latencies_s[-_MAX_BEHAVIOR_EVENTS:]
            if attention is not None:
                beh.attention_samples.append(attention)
                if len(beh.attention_samples) > _MAX_BEHAVIOR_EVENTS:
                    beh.attention_samples = beh.attention_samples[-_MAX_BEHAVIOR_EVENTS:]
            if asked_question:
                beh.questions_asked += 1
            if saw_slide:
                beh.slides_seen += 1

    def purge_expired(self, *, now=None, default_retention_days=None) -> dict:
        """Enforce retention: drop consent records past their window, revoke the
        corresponding grant, and delete any student whose data is no longer
        covered by an active (non-expired) consent. Returns a purge report."""
        from aoep_shared.retention import PurgeReport, is_expired

        # BUG 11 + 15 FIX: hold the lock for the entire purge so the
        # _consent_log swap and the student-key iteration are atomic with
        # respect to concurrent record_consent / upsert_student calls.
        with self._lock:
            report = PurgeReport(scanned=len(self._consent_log))
            kept: list[ConsentRecord] = []
            for rec in self._consent_log:
                if is_expired(rec.recorded_at, rec.retention_days, now=now,
                              default_days=default_retention_days):
                    report.consent_records_purged += 1
                    mem = self._students.get(rec.student_id)
                    if mem is not None:
                        mem.consents[rec.scope] = False   # revoke on expiry
                else:
                    kept.append(rec)
            self._consent_log = kept

            # Delete students whose data is no longer covered by any active
            # consent (data minimisation / storage limitation). A student with
            # no consent records at all is left untouched.
            students_with_records = {r.student_id for r in self._consent_log}
            for sid in list(self._students.keys()):
                mem = self._students[sid]
                ever_had = any(mem.consents)  # had at least one consent decision
                still_active = any(mem.consents.values())
                if ever_had and not still_active and sid not in students_with_records:
                    del self._students[sid]
                    report.students_purged += 1

        return {"scanned": report.scanned,
                "consent_records_purged": report.consent_records_purged,
                "students_purged": report.students_purged}

    def learner_signals(self, student_id: str, topic: str) -> LearnerSignals:
        """Aggregate this student's behavior on ``topic`` into adaptive signals."""
        mem = self._students.get(student_id)
        beh = mem.behavior.get(topic, TopicBehavior()) if mem else TopicBehavior()
        mastery = mem.mastery.get(topic, 0.5) if mem else 0.5
        return signals_from_events(
            quiz_outcomes=beh.quiz_outcomes,
            response_latencies_s=beh.response_latencies_s,
            attention_samples=beh.attention_samples,
            questions_asked=beh.questions_asked,
            slides_seen=max(1, beh.slides_seen),
            topic_mastery=mastery,
        )
