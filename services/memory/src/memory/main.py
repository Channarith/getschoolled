"""Memory FastAPI app: profiles, consent records, and mastery updates."""

from __future__ import annotations

import os

from aoep_shared.compliance import compliance_summary
from aoep_shared.flags import FlagStore, require_admin
from aoep_shared.legal import NOTICES, REQUIRED_NOTICE_IDS, AcceptanceStore, notice_versions
from aoep_shared.schemas import ConsentRecord, ConsentScope, Region
from aoep_shared.service import create_service
from aoep_shared.survey import SurveyResponse, SurveyStore, template as survey_template
from aoep_shared.testsupport import test_endpoints_enabled
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from .store import MemoryStore

app = create_service("memory")
app.state.store = MemoryStore()
app.state.acceptances = AcceptanceStore()
app.state.flags = FlagStore()
app.state.surveys = SurveyStore()


def _admin_secret() -> str:
    return os.environ.get("ADMIN_SECRET", "dev-admin-secret")


def require_admin_header(x_admin_secret: str = Header(default="")) -> str:
    """FastAPI dependency: gate administrative writes behind the admin secret."""
    if not require_admin(x_admin_secret, _admin_secret()):
        raise HTTPException(status_code=401, detail="invalid or missing admin secret")
    return "admin"


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


# --------------------------------------------------------------------------- #
# Legal notices + user agreement/acceptance, and the region compliance summary
# --------------------------------------------------------------------------- #
@app.get("/legal/notices")
def legal_notices() -> dict:
    return {
        "required": list(REQUIRED_NOTICE_IDS),
        "notices": [
            {"id": n.id, "title": n.title, "version": n.version,
             "summary": n.summary, "path": n.path}
            for n in NOTICES
        ],
    }


class AcceptRequest(BaseModel):
    user_id: str
    notice_ids: list[str]


@app.post("/legal/accept")
def legal_accept(req: AcceptRequest) -> dict:
    rec = app.state.acceptances.accept(req.user_id, req.notice_ids)
    return {"user_id": rec.user_id, "accepted": rec.accepted,
            "all_required_accepted": app.state.acceptances.has_accepted_required(req.user_id),
            "outstanding": app.state.acceptances.outstanding(req.user_id)}


@app.get("/legal/acceptance/{user_id}")
def legal_acceptance(user_id: str) -> dict:
    rec = app.state.acceptances.get(user_id)
    return {"user_id": user_id,
            "accepted": rec.accepted if rec else {},
            "all_required_accepted": app.state.acceptances.has_accepted_required(user_id),
            "outstanding": app.state.acceptances.outstanding(user_id),
            "current_versions": notice_versions()}


@app.get("/compliance/{region}")
def compliance(region: str) -> dict:
    return compliance_summary(region)


class PurgeRequest(BaseModel):
    # Optional fallback window for records that carry no explicit retention_days.
    default_retention_days: int | None = None


@app.post("/retention/purge")
def retention_purge(req: PurgeRequest) -> dict:
    """Enforce data retention: delete data past its retention window.

    Intended to run on a schedule (cron / k8s CronJob) - see
    scripts/retention_purge.py and infra/k8s/retention-cronjob.yaml.
    """
    return app.state.store.purge_expired(default_retention_days=req.default_retention_days)


# --------------------------------------------------------------------------- #
# Administrative feature flags (secret-gated writes; public/eval reads)
# --------------------------------------------------------------------------- #
@app.get("/flags/evaluate")
def flags_evaluate(subject: str | None = None, tier: str | None = None) -> dict:
    """Resolve all non-admin flags for a request context (used by the apps)."""
    return {
        "subject": subject,
        "tier": tier,
        "flags": app.state.flags.evaluate_all(subject=subject, tier=tier),
    }


@app.get("/flags/{key}")
def flag_get(key: str, subject: str | None = None, tier: str | None = None) -> dict:
    if app.state.flags.spec(key) is None:
        raise HTTPException(status_code=404, detail="unknown flag")
    return {
        "key": key,
        "value": app.state.flags.resolve(key, subject=subject, tier=tier),
        "spec": app.state.flags.describe(key),
    }


@app.get("/admin/flags")
def admin_list_flags(_: str = Depends(require_admin_header)) -> dict:
    """Full flag catalog with runtime state (admin-only, includes hidden flags)."""
    return {"flags": app.state.flags.list_specs(include_admin=True)}


class SetFlagRequest(BaseModel):
    enabled: bool | None = None
    value: object | None = None
    rollout_pct: int | None = None
    tiers: list[str] | None = None
    clear_value: bool = False


@app.put("/admin/flags/{key}")
def admin_set_flag(key: str, req: SetFlagRequest,
                   _: str = Depends(require_admin_header)) -> dict:
    try:
        app.state.flags.set_flag(
            key, enabled=req.enabled, value=req.value, rollout_pct=req.rollout_pct,
            tiers=req.tiers, clear_value=req.clear_value, actor="admin",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown flag")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return app.state.flags.describe(key)


class OverrideRequest(BaseModel):
    subject: str
    value: object


@app.post("/admin/flags/{key}/override")
def admin_override_flag(key: str, req: OverrideRequest,
                        _: str = Depends(require_admin_header)) -> dict:
    try:
        app.state.flags.set_override(key, req.subject, req.value, actor="admin")
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown flag")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return app.state.flags.describe(key)


@app.post("/admin/flags/{key}/reset")
def admin_reset_flag(key: str, _: str = Depends(require_admin_header)) -> dict:
    if app.state.flags.spec(key) is None:
        raise HTTPException(status_code=404, detail="unknown flag")
    app.state.flags.reset(key)
    return app.state.flags.describe(key)


# --------------------------------------------------------------------------- #
# End-of-class survey (gated by engagement.post_class_survey flag) + insights
# --------------------------------------------------------------------------- #
@app.get("/survey/post-class")
def survey_post_class(subject: str | None = None, tier: str | None = None) -> dict:
    """Return the survey template IF the post-class survey flag is enabled.

    The client uses `enabled` to decide whether to prompt the learner.
    """
    enabled = bool(app.state.flags.resolve(
        "engagement.post_class_survey", subject=subject, tier=tier))
    return {"enabled": enabled, "template": survey_template() if enabled else None}


class SurveySubmit(BaseModel):
    course_id: str
    overall: int
    class_type: str = "self_paced"
    subject: str = ""
    student_id: str | None = None
    clarity: int | None = None
    pace: str | None = None
    would_recommend: bool | None = None
    suggestion: str = ""


@app.post("/survey/post-class")
def survey_submit(req: SurveySubmit) -> dict:
    try:
        resp = app.state.surveys.submit(SurveyResponse(**req.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": resp.id, "course_id": resp.course_id, "recorded": True}


@app.get("/survey/summary/{course_id}")
def survey_course_summary(course_id: str) -> dict:
    return app.state.surveys.course_summary(course_id)


@app.get("/admin/survey/insights")
def survey_insights(_: str = Depends(require_admin_header)) -> dict:
    """Multi-dimensional data-mart of survey responses (admin-only).

    Available when the data-mining flag is on; otherwise reports it as disabled.
    """
    mining_on = bool(app.state.flags.resolve("data.multidim_datamart"))
    return {"data_mining_enabled": mining_on, "datamart": app.state.surveys.datamart()}


# --------------------------------------------------------------------------- #
# Automation/E2E test hooks: deterministic reset + seed of in-memory state.
# Double-gated: admin secret AND test endpoints must be enabled for the process.
# --------------------------------------------------------------------------- #
def require_test_mode() -> None:
    if not test_endpoints_enabled(app.state.config):
        raise HTTPException(status_code=403, detail="test endpoints are disabled")


@app.post("/admin/test/reset")
def test_reset(scope: str = "all", _: str = Depends(require_admin_header)) -> dict:
    """Reset in-memory state so automated tests start from a known baseline.

    scope: all | flags | surveys | acceptances | store
    """
    require_test_mode()
    reset: list[str] = []
    if scope in ("all", "flags"):
        app.state.flags = FlagStore()
        reset.append("flags")
    if scope in ("all", "surveys"):
        app.state.surveys = SurveyStore()
        reset.append("surveys")
    if scope in ("all", "acceptances"):
        app.state.acceptances = AcceptanceStore()
        reset.append("acceptances")
    if scope in ("all", "store"):
        app.state.store = MemoryStore()
        reset.append("store")
    return {"reset": reset}


class SeedRequest(BaseModel):
    flags: dict[str, dict] | None = None       # key -> {enabled,value,rollout_pct,tiers}
    surveys: list[dict] | None = None          # SurveyResponse-shaped dicts


@app.post("/admin/test/seed")
def test_seed(req: SeedRequest, _: str = Depends(require_admin_header)) -> dict:
    """Seed deterministic fixtures (flags + survey responses) for automation."""
    require_test_mode()
    seeded = {"flags": 0, "surveys": 0}
    for key, patch in (req.flags or {}).items():
        try:
            app.state.flags.set_flag(
                key, enabled=patch.get("enabled"), value=patch.get("value"),
                rollout_pct=patch.get("rollout_pct"), tiers=patch.get("tiers"),
                actor="test-seed",
            )
            seeded["flags"] += 1
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"flag {key}: {exc}")
    for row in (req.surveys or []):
        try:
            app.state.surveys.submit(SurveyResponse(**row))
            seeded["surveys"] += 1
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=f"survey: {exc}")
    return {"seeded": seeded}


@app.post("/mastery")
def update_mastery(req: MasteryUpdate) -> dict:
    score = app.state.store.update_mastery(req.student_id, req.topic, req.correct)
    return {"student_id": req.student_id, "topic": req.topic, "mastery": score}


class BehaviorEvent(BaseModel):
    student_id: str
    topic: str
    quiz_correct: bool | None = None
    response_latency_s: float | None = None
    attention: float | None = None
    asked_question: bool = False
    saw_slide: bool = False


@app.post("/behavior")
def record_behavior(req: BehaviorEvent) -> dict:
    app.state.store.record_behavior(
        req.student_id,
        req.topic,
        quiz_correct=req.quiz_correct,
        response_latency_s=req.response_latency_s,
        attention=req.attention,
        asked_question=req.asked_question,
        saw_slide=req.saw_slide,
    )
    return {"student_id": req.student_id, "topic": req.topic, "recorded": True}


@app.get("/learner/{student_id}/{topic}")
def learner_signals(student_id: str, topic: str) -> dict:
    """Aggregated learning-behavior signals used by the adaptive policy."""
    s = app.state.store.learner_signals(student_id, topic)
    return {
        "student_id": student_id,
        "topic": topic,
        "topic_mastery": s.topic_mastery,
        "quiz_accuracy": s.quiz_accuracy,
        "avg_response_latency_s": s.avg_response_latency_s,
        "attention_trend": s.attention_trend,
        "question_rate": s.question_rate,
        "skill": s.skill(),
    }
