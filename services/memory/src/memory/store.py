"""In-memory profile / consent / mastery store (phase0).

Persistence is Postgres + pgvector in real deployments (see db/migrations); this
process-local store keeps the API shape and the policy logic testable offline.
The mastery score uses a simple exponential moving average over quiz outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from aoep_shared.schemas import ConsentRecord, ConsentScope


@dataclass
class StudentMemory:
    student_id: str
    display_name: str
    # topic -> mastery in [0, 1]
    mastery: dict[str, float] = field(default_factory=dict)
    # scope -> granted?
    consents: dict[ConsentScope, bool] = field(default_factory=dict)


class MemoryStore:
    def __init__(self) -> None:
        self._students: dict[str, StudentMemory] = {}
        self._consent_log: list[ConsentRecord] = []

    def upsert_student(self, student_id: str, display_name: str) -> StudentMemory:
        mem = self._students.get(student_id)
        if mem is None:
            mem = StudentMemory(student_id=student_id, display_name=display_name)
            self._students[student_id] = mem
        else:
            mem.display_name = display_name
        return mem

    def get(self, student_id: str) -> StudentMemory | None:
        return self._students.get(student_id)

    def record_consent(self, record: ConsentRecord) -> None:
        self._consent_log.append(record)
        mem = self._students.get(record.student_id)
        if mem is None:
            mem = self.upsert_student(record.student_id, record.student_id)
        mem.consents[record.scope] = record.granted

    def has_consent(self, student_id: str, scope: ConsentScope) -> bool:
        mem = self._students.get(student_id)
        return bool(mem and mem.consents.get(scope, False))

    def update_mastery(
        self, student_id: str, topic: str, correct: bool, *, alpha: float = 0.4
    ) -> float:
        mem = self._students.get(student_id)
        if mem is None:
            mem = self.upsert_student(student_id, student_id)
        prior = mem.mastery.get(topic, 0.0)
        target = 1.0 if correct else 0.0
        updated = (1 - alpha) * prior + alpha * target
        mem.mastery[topic] = updated
        return updated
