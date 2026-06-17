"""Memory FastAPI app: profiles, consent records, and mastery updates."""

from __future__ import annotations

from aoep_shared.schemas import ConsentRecord, ConsentScope, Region
from aoep_shared.service import create_service
from pydantic import BaseModel

from .store import MemoryStore

app = create_service("memory")
app.state.store = MemoryStore()


class StudentUpsert(BaseModel):
    student_id: str
    display_name: str


class ConsentUpsert(BaseModel):
    student_id: str
    scope: ConsentScope
    granted: bool
    region: Region = Region.OTHER
    written: bool = False
    retention_days: int | None = None


class MasteryUpdate(BaseModel):
    student_id: str
    topic: str
    correct: bool


@app.post("/students")
def upsert_student(req: StudentUpsert) -> dict:
    mem = app.state.store.upsert_student(req.student_id, req.display_name)
    return {"student_id": mem.student_id, "display_name": mem.display_name}


@app.post("/consent")
def record_consent(req: ConsentUpsert) -> dict:
    record = ConsentRecord(
        student_id=req.student_id,
        scope=req.scope,
        granted=req.granted,
        region=req.region,
        written=req.written,
        retention_days=req.retention_days,
    )
    app.state.store.record_consent(record)
    return {"student_id": req.student_id, "scope": req.scope, "granted": req.granted}


@app.get("/consent/{student_id}/{scope}")
def has_consent(student_id: str, scope: ConsentScope) -> dict:
    return {
        "student_id": student_id,
        "scope": scope,
        "granted": app.state.store.has_consent(student_id, scope),
    }


@app.post("/mastery")
def update_mastery(req: MasteryUpdate) -> dict:
    score = app.state.store.update_mastery(req.student_id, req.topic, req.correct)
    return {"student_id": req.student_id, "topic": req.topic, "mastery": score}
