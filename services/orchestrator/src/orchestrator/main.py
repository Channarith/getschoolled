"""Orchestrator FastAPI app.

Owns class-session lifecycle and exposes the Director decision endpoint. It
issues LiveKit join tokens via the MediaProvider so the same flow works against a
local LiveKit container or a cloud cluster.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict

from aoep_shared.adaptive import AdaptivePolicy, Difficulty, LearnerSignals, Pacing
from aoep_shared.assessment import (
    GradeResult,
    QuizItem,
    definition_items_from_passages,
    grade,
)
from aoep_shared.assessment_policy import (
    AssessmentStage,
    CheckpointPolicy,
    EvidenceDomain,
    decide_course_pass,
    evaluate_checkpoint,
    present_item,
    select_assessment_format,
)
from aoep_shared.internal_auth import require_internal
from aoep_shared.schemas import ClassType
from aoep_shared.service import create_service
from fastapi import BackgroundTasks, Depends, File, Form, Header, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .curriculum import CourseKSB, Lesson, Slide
from .director import ClassContext, Director, LessonState
from .teaching import Answer, Reengagement, SessionView, TeachingSessions

app = create_service("orchestrator")

from aoep_shared.optimization import OptimizationLedger  # noqa: E402

app.state.optimization = OptimizationLedger()
app.state.assessment_runs = {}
app.state.assessment_results = []
# Server-side quiz item cache keyed by item_id.  Correct answer indices are
# stored here so they are never sent to or trusted from the client.
# Capped at 50 000 entries; cleared when full to prevent unbounded growth.
app.state.quiz_items: dict = {}

import os  # noqa: E402
import threading as _threading  # noqa: E402

from aoep_shared.hil import (  # noqa: E402
    AutonomyLevel,
    ReviewItem,
    ReviewKind,
    ReviewQueue,
    should_escalate,
)

app.state.hil = ReviewQueue()
try:
    app.state.autonomy = AutonomyLevel(os.environ.get("HIL_AUTONOMY", "autonomous"))
except ValueError:
    app.state.autonomy = AutonomyLevel.AUTONOMOUS

_HUMAN_REQUEST_CUES = ("talk to a human", "speak to a human", "real person",
                       "human teacher", "real teacher")


@app.get("/api/disclosure")
def disclosure(persona: str = "friendly", human_of_record: str | None = None) -> dict:
    """AI-disclosure metadata for the transparency badge / page (Phase 1)."""
    from aoep_shared.disclosure import disclosure_from_config

    d = disclosure_from_config(
        app.state.config, persona=persona, human_of_record=human_of_record
    )
    return {**d.model_dump(), "line": d.disclosure_line()}

# Live-class teaching loop (web-facing). Built lazily so /health and the other
# endpoints don't pay curriculum/RAG load cost unless a class is used.
_sessions: TeachingSessions | None = None
_sessions_lock = _threading.Lock()


def get_sessions() -> TeachingSessions:
    global _sessions
    if _sessions is None:
        with _sessions_lock:
            if _sessions is None:
                _sessions = TeachingSessions(
                    app.state.factory, memory_base_url=app.state.config.memory_base_url
                )
    return _sessions


class CreateClassRequest(BaseModel):
    title: str
    class_type: ClassType = ClassType.GROUP
    language: str = "en"
    persona: str = "friendly"


class CreateClassResponse(BaseModel):
    class_id: str
    room: str
    title: str
    class_type: ClassType
    language: str
    persona: str


class JoinResponse(BaseModel):
    room: str
    identity: str
    token: str
    url: str


class DirectorTickRequest(BaseModel):
    class_type: ClassType = ClassType.GROUP
    slides_total: int = 1
    slide_index: int = 0
    pending_questions: int = 0
    attention: float = 1.0
    slides_since_quiz: int = 0


class DirectorTickResponse(BaseModel):
    next_state: LessonState


@app.post("/classes", response_model=CreateClassResponse)
def create_class(req: CreateClassRequest) -> CreateClassResponse:
    class_id = uuid.uuid4().hex
    room = f"class-{class_id[:8]}"
    return CreateClassResponse(
        class_id=class_id,
        room=room,
        title=req.title,
        class_type=req.class_type,
        language=req.language,
        persona=req.persona,
    )


@app.get("/classes/{room}/join", response_model=JoinResponse)
def join_class(room: str, identity: str) -> JoinResponse:
    media = app.state.factory.media()
    token = media.issue_token(room=room, identity=identity)
    return JoinResponse(
        room=token.room, identity=token.identity, token=token.token, url=token.url
    )


# --------------------------------------------------------------------------- #
# Live-class teaching loop (consumed by apps/web)
# --------------------------------------------------------------------------- #
class StartSessionRequest(BaseModel):
    lesson_id: str
    class_type: ClassType = ClassType.GROUP
    # When set, the live loop records per-student behavior/mastery to the memory
    # service so quizzes + pacing adapt to this learner.
    student_id: str | None = None
    profile_score: str = ""
    session_length: str = ""
    session_budget_min: int | None = None
    observed_pace: str = ""

    model_config = {"extra": "forbid"}


class LessonPlanRequest(BaseModel):
    profile_score: str = ""
    session_length: str = "medium"
    session_budget_min: int | None = None
    observed_pace: str = ""

    model_config = {"extra": "forbid"}


class AskRequest(BaseModel):
    text: str
    language: str = "en"


@app.get("/api/lessons", response_model=list[Lesson])
def api_lessons(q: str = "", language: str = "", audience: str = "") -> list[Lesson]:
    lessons = get_sessions().list_lessons()
    if q:
        q_lower = q.lower()
        lessons = [l for l in lessons if q_lower in l.title.lower() or q_lower in (l.audience or "").lower() or q_lower in (l.track or "").lower()]
    if language:
        lessons = [l for l in lessons if l.language == language]
    if audience:
        lessons = [l for l in lessons if l.audience == audience]
    return lessons


@app.get("/api/lessons/{lesson_id}/ksb", response_model=CourseKSB)
def api_lesson_ksb(lesson_id: str) -> CourseKSB:
    """Return the course's occupational standard (duties mapped to KSBs).

    Mirrors the UK apprenticeship standard format; present for corporate
    programmes that ship a ksb.json next to their lesson.
    """
    ksb = get_sessions().curriculum.ksb_for(lesson_id)
    if ksb is None:
        raise HTTPException(status_code=404, detail=f"no KSB for lesson {lesson_id}")
    return ksb


@app.post("/api/lessons/{lesson_id}/plan")
def api_lesson_plan(lesson_id: str, req: LessonPlanRequest) -> dict:
    """Build a shorter or deeper path through the same canonical lesson."""
    from aoep_shared.catalog_selection import (
        profile_dimensions,
        resolve_session_budget,
    )
    from aoep_shared.lesson_depth import (
        plan_slide_indices,
        planned_duration_minutes,
    )

    lesson = get_sessions().curriculum.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail=f"unknown lesson {lesson_id}")
    try:
        dimensions = profile_dimensions(
            req.profile_score, session_length=req.session_length,
        )
        budget = resolve_session_budget(
            dimensions.get("session_length", req.session_length),
            explicit_minutes=req.session_budget_min,
            observed_pace=req.observed_pace,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    indices = plan_slide_indices(lesson.slides, budget)
    slides = [
        lesson.slides[index].model_copy(update={"index": position}).model_dump()
        for position, index in enumerate(indices)
    ]
    return {
        "lesson_id": lesson_id,
        "title": lesson.title,
        "profile_score": req.profile_score,
        "session_budget_min": budget,
        "estimated_duration_min": planned_duration_minutes(len(indices)),
        "source_slide_count": len(lesson.slides),
        "planned_slide_count": len(slides),
        "source_slide_indices": indices,
        "slides": slides,
        "mastery_target": "unchanged",
        "coverage_strategy": "evenly_spaced_teaching_slides",
    }


@app.get("/api/lessons/{lesson_id}/accreditation")
def api_lesson_accreditation(lesson_id: str) -> dict:
    """Return whether a lesson awards accreditation and requires a registered account.

    HARD RULE: certifiable / certification courses require sign-up. Guests may
    still take sample (non-certifiable) courses.
    """
    from aoep_shared.accreditation import (
        certification_meta,
        is_certifiable_lesson,
        requires_registered_account,
    )

    body, ceu = certification_meta(lesson_id)
    certifiable = is_certifiable_lesson(lesson_id)
    return {
        "lesson_id": lesson_id,
        "certifiable": certifiable,
        "requires_registered_account": requires_registered_account(lesson_id),
        "certification_body": body,
        "ceu_credits": ceu,
    }


@app.post("/api/sessions", response_model=SessionView)
def api_start_session(
    req: StartSessionRequest,
    authorization: str = Header(default=""),
) -> SessionView:
    # HARD RULE: accreditation / certification courses require a registered
    # account. Guests may start sample (non-certifiable) lessons only.
    from aoep_shared.accreditation import (
        ACCREDITATION_ACCOUNT_REQUIRED_DETAIL,
        may_start_for_accreditation,
    )

    account_id = _assessment_account_id(authorization)
    allowed, reason = may_start_for_accreditation(
        req.lesson_id, account_id=account_id or None,
    )
    if not allowed:
        raise HTTPException(
            status_code=401,
            detail=ACCREDITATION_ACCOUNT_REQUIRED_DETAIL,
            headers={"X-AOEP-Gate": reason},
        )

    sessions = get_sessions()
    try:
        budget = req.session_budget_min
        if budget is None and (req.profile_score or req.session_length):
            from aoep_shared.catalog_selection import (
                profile_dimensions,
                resolve_session_budget,
            )

            dimensions = profile_dimensions(
                req.profile_score, session_length=req.session_length,
            )
            budget = resolve_session_budget(
                dimensions.get("session_length", req.session_length or "medium"),
                observed_pace=req.observed_pace,
            )
        state = sessions.start_session(
            req.lesson_id,
            req.class_type.value,
            student_id=req.student_id,
            session_budget_min=budget,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {req.lesson_id}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SessionView(
        session=state,
        lesson=sessions.lesson_for(state.session_id),
        slide=sessions.current_slide(state.session_id),
    )


@app.get("/api/sessions/{session_id}", response_model=SessionView)
def api_get_session(session_id: str, _=Depends(require_internal)) -> SessionView:
    sessions = get_sessions()
    try:
        state = sessions.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")
    return SessionView(
        session=state,
        lesson=sessions.lesson_for(session_id),
        slide=sessions.current_slide(session_id),
    )


@app.post("/api/sessions/{session_id}/advance", response_model=Slide)
def api_advance(session_id: str) -> Slide:
    try:
        return get_sessions().advance(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")


@app.post("/api/sessions/{session_id}/ask/stream")
async def api_ask_stream(session_id: str, req: AskRequest, request: Request):
    """Server-Sent Events stream of the conversational agent's answer for the
    real-time voice assistant (start speaking on the first tokens). Each event is
    `data: {json}\\n\\n`; a final {"type":"done", ...} carries the guarded answer +
    grounding metadata. Powered by the Nemotron agent when configured."""
    import json as _json

    from fastapi.responses import StreamingResponse

    sessions = get_sessions()
    try:
        sessions.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")

    async def _events():
        for event in sessions.ask_stream(session_id, req.text, language=req.language):
            if await request.is_disconnected():
                break
            yield f"data: {_json.dumps(event)}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/sessions/{session_id}/ask", response_model=Answer)
def api_ask(session_id: str, req: AskRequest) -> Answer:
    sessions = get_sessions()
    try:
        answer = sessions.ask(session_id, req.text, language=req.language)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")

    # Human-in-the-loop gate (Phase 11): route risky/low-confidence/sensitive or
    # student-requested answers to a human review queue (per the autonomy level).
    student_requested = any(c in req.text.lower() for c in _HUMAN_REQUEST_CUES)
    if should_escalate(
        autonomy=app.state.autonomy,
        risk=answer.hallucination_risk,
        ai_confidence=1.0 - answer.hallucination_risk,
        student_requested=student_requested,
    ):
        item = app.state.hil.enqueue(ReviewItem(
            kind=ReviewKind.ANSWER,
            payload={"session_id": session_id, "question": req.text, "text": answer.text,
                     "citations": answer.citations},
            ai_confidence=round(1.0 - answer.hallucination_risk, 3),
            risk=answer.hallucination_risk,
        ))
        answer.pending_review = True
        answer.review_id = item.id

    # AI-agent reward: the teacher grants a few points for a substantive,
    # on-topic question that produced a grounded answer (bounded per session).
    # We MINT a short-lived, HMAC-signed voucher; the learner's client redeems it
    # at identity /rewards/grant, which verifies the signature before crediting -
    # so the agent authorizes the reward and a user cannot forge or replay it.
    _maybe_grant_reward(session_id, req.text, answer)
    return answer


@app.post("/api/sessions/{session_id}/reengage", response_model=Reengagement)
def api_reengage(session_id: str) -> Reengagement:
    """Re-engage a drifting learner (the REENGAGING beat): a slide-grounded recap
    + prompt. Deterministic; no model server required."""
    try:
        return get_sessions().reengage(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")


from collections import OrderedDict as _ODict  # noqa: E402

_assessment_start_locks: _ODict[str, _threading.Lock] = _ODict()
_assessment_locks_mu = _threading.Lock()
_MAX_ASSESSMENT_LOCKS = 5_000


def _assessment_lock_for(key: str) -> _threading.Lock:
    with _assessment_locks_mu:
        if key in _assessment_start_locks:
            _assessment_start_locks.move_to_end(key)
            return _assessment_start_locks[key]
        lk = _threading.Lock()
        _assessment_start_locks[key] = lk
        if len(_assessment_start_locks) > _MAX_ASSESSMENT_LOCKS:
            _assessment_start_locks.popitem(last=False)  # evict oldest, never in-flight
        return lk


_AGENT_REWARD_POINTS = int(os.environ.get("AGENT_REWARD_POINTS", "10"))
_AGENT_REWARD_SESSION_CAP = int(os.environ.get("AGENT_REWARD_SESSION_CAP", "30"))
_session_reward_total: _ODict[str, int] = _ODict()
_reward_lock = _threading.Lock()
_MAX_SESSION_REWARD_ENTRIES = 10_000


def _maybe_grant_reward(session_id: str, question: str, answer: Answer) -> None:
    key = os.environ.get("INTERNAL_TOKEN_KEY", "")
    if not key or not answer.grounded or answer.pending_review:
        return
    if len(question.strip()) < 12:   # ignore trivial/empty questions
        return
    with _reward_lock:
        if len(_session_reward_total) >= _MAX_SESSION_REWARD_ENTRIES:
            _session_reward_total.pop(next(iter(_session_reward_total)))  # evict oldest
        awarded = _session_reward_total.get(session_id, 0)
        if awarded >= _AGENT_REWARD_SESSION_CAP:
            return
        pts = min(_AGENT_REWARD_POINTS, _AGENT_REWARD_SESSION_CAP - awarded)
        _session_reward_total[session_id] = awarded + pts
    from aoep_shared.auth import sign_token

    reason = "Great question — keep engaging!"
    grant = sign_token(
        {"scope": "reward", "points": pts, "reason": reason,
         "ref": session_id, "nonce": uuid.uuid4().hex},
        key.encode("utf-8"), ttl_s=3600,
    )
    answer.reward = {"points": pts, "reason": reason, "grant_token": grant}


# --------------------------------------------------------------------------- #
# Embodiment: render a teaching beat onto the screen avatar or a robot (P14)
# --------------------------------------------------------------------------- #
class EmbodyRequest(BaseModel):
    text: str
    gesture: str | None = None
    language: str = "en"


@app.post("/api/embody")
def embody(req: EmbodyRequest) -> dict:
    from aoep_shared.providers.embodiment import narrate

    provider = app.state.factory.embodiment()
    actions = narrate(provider, req.text, gesture=req.gesture, language=req.language)
    return {"embodiment": provider.info().impl,
            "actions": [{"modality": a.modality, "payload": a.payload} for a in actions]}


# --------------------------------------------------------------------------- #
# Human-in-the-loop review queue (co-teaching, Phase 11)
# --------------------------------------------------------------------------- #
def _review_dict(it) -> dict:
    return {"id": it.id, "kind": it.kind.value, "payload": it.payload,
            "ai_confidence": it.ai_confidence, "risk": it.risk, "subject": it.subject,
            "status": it.status.value, "final_payload": it.final_payload,
            "decided_by": it.decided_by, "created_at": it.created_at}


@app.get("/api/hil/queue", dependencies=[Depends(require_internal)])
def hil_queue(status: str | None = None) -> dict:
    from aoep_shared.hil import ReviewStatus

    st = ReviewStatus(status) if status else None
    return {"autonomy": app.state.autonomy.value,
            "items": [_review_dict(i) for i in app.state.hil.list(st)]}


class HilDecisionRequest(BaseModel):
    action: str                       # approve | edit | reject | takeover
    edited_payload: dict | None = None
    decided_by: str = "human"


@app.post("/api/hil/{item_id}/decision",
          dependencies=[Depends(require_internal)])
def hil_decision(item_id: str, req: HilDecisionRequest) -> dict:
    try:
        item = app.state.hil.decide(item_id, req.action, edited_payload=req.edited_payload,
                                    decided_by=req.decided_by)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown review item")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _review_dict(item)


# --------------------------------------------------------------------------- #
# Optimization ledger (track accuracy per stage; promote / revert)
# --------------------------------------------------------------------------- #
class CommitStepRequest(BaseModel):
    stage: str
    params: dict = {}
    metrics: dict = {}
    parent: str | None = None


def _step_dict(s) -> dict:
    return {"step_id": s.step_id, "stage": s.stage, "params": s.params,
            "metrics": s.metrics, "parent": s.parent, "created_at": s.created_at}


@app.post("/api/optimization/commit",
          dependencies=[Depends(require_internal)])
def optimization_commit(req: CommitStepRequest) -> dict:
    ledger = app.state.optimization
    step = ledger.commit(req.stage, req.params, req.metrics, parent=req.parent)
    promoted = ledger.promote_if_better(step)
    return {"step": _step_dict(step), "promoted": promoted,
            "champion": _step_dict(ledger.champion(req.stage))}


@app.get("/api/optimization/champion/{stage}")
def optimization_champion(stage: str) -> dict:
    champ = app.state.optimization.champion(stage)
    return {"stage": stage, "champion": _step_dict(champ) if champ else None}


@app.get("/api/optimization/history")
def optimization_history(stage: str | None = None) -> dict:
    return {"steps": [_step_dict(s) for s in app.state.optimization.history(stage)]}


class RevertRequest(BaseModel):
    stage: str
    step_id: str


@app.post("/api/optimization/revert",
          dependencies=[Depends(require_internal)])
def optimization_revert(req: RevertRequest) -> dict:
    try:
        step = app.state.optimization.revert(req.stage, req.step_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"reverted_to": _step_dict(step)}


# --------------------------------------------------------------------------- #
# Hallucination guard (groundedness check)
# --------------------------------------------------------------------------- #
class GroundingRequest(BaseModel):
    answer: str
    context: list[str] = []
    support_threshold: float = 0.5
    pass_threshold: float = 0.7


@app.post("/api/groundedness/check")
def groundedness_check(req: GroundingRequest) -> dict:
    from aoep_shared.groundedness import check_grounding

    report = check_grounding(
        req.answer, req.context,
        support_threshold=req.support_threshold, pass_threshold=req.pass_threshold,
    )
    return {
        "groundedness": report.groundedness,
        "hallucination_risk": report.hallucination_risk,
        "grounded": report.grounded,
        "unsupported": report.unsupported,
    }


# --------------------------------------------------------------------------- #
# Slang / idiom understanding
# --------------------------------------------------------------------------- #
class SlangRequest(BaseModel):
    text: str
    language: str = "en"
    region: str | None = None


class SlangResponse(BaseModel):
    original: str
    plain: str
    detections: list[dict]


@app.post("/api/slang/normalize", response_model=SlangResponse)
def slang_normalize(req: SlangRequest) -> SlangResponse:
    from aoep_shared.slang import default_lexicon

    norm = default_lexicon().normalize(req.text, language=req.language, region=req.region)
    return SlangResponse(
        original=norm.original,
        plain=norm.plain,
        detections=[
            {"phrase": d.phrase, "meaning": d.meaning, "region": d.region, "kind": d.kind}
            for d in norm.detections
        ],
    )


@app.post("/director/tick", response_model=DirectorTickResponse)
def director_tick(req: DirectorTickRequest) -> DirectorTickResponse:
    director = Director()
    ctx = ClassContext(
        class_type=req.class_type,
        slides_total=req.slides_total,
        slide_index=req.slide_index,
        pending_questions=req.pending_questions,
        attention=req.attention,
        slides_since_quiz=req.slides_since_quiz,
    )
    return DirectorTickResponse(next_state=director.decide(ctx))


# --------------------------------------------------------------------------- #
# Phase 4 - adaptive pacing/difficulty plan
# --------------------------------------------------------------------------- #
class PlanRequest(DirectorTickRequest):
    topic_mastery: float = 0.5
    quiz_accuracy: float = 0.5
    avg_response_latency_s: float = 5.0
    attention_trend: float = 1.0
    question_rate: float = 0.0
    declared_pace: str = "moderate"
    adaptation: dict = {}
    course_complexity: int = 3
    wellness_state: str = "ok"


class PlanResponse(BaseModel):
    next_state: LessonState
    pacing: Pacing
    difficulty: Difficulty
    reteach: bool
    reasons: list[str]


@app.post("/director/plan", response_model=PlanResponse)
def director_plan(req: PlanRequest) -> PlanResponse:
    director = Director()
    ctx = ClassContext(
        class_type=req.class_type,
        slides_total=req.slides_total,
        slide_index=req.slide_index,
        pending_questions=req.pending_questions,
        attention=req.attention,
        slides_since_quiz=req.slides_since_quiz,
    )
    signals = LearnerSignals(
        topic_mastery=req.topic_mastery,
        quiz_accuracy=req.quiz_accuracy,
        avg_response_latency_s=req.avg_response_latency_s,
        attention_trend=req.attention_trend,
        question_rate=req.question_rate,
    )
    from aoep_shared.learner_adaptation import LearnerAdaptation, merge_pacing_plan

    adapt = LearnerAdaptation(**{
        k: req.adaptation.get(k)
        for k in (
            "learning_goals", "goal_timeline", "observed_pace", "avg_minutes_per_lesson",
            "completion_samples", "strategy_wins", "strategy_losses", "known_triggers",
            "wellness_state", "wellness_reason", "wellness_updated_at",
            "profile_revision",
        )
        if k in req.adaptation
    }) if req.adaptation else None
    if adapt and req.adaptation.get("failed_approaches"):
        from aoep_shared.learner_adaptation import FailedApproach
        adapt.failed_approaches = [
            FailedApproach(**f) for f in req.adaptation["failed_approaches"]
        ]
    if adapt and req.adaptation.get("sensitivity_rules"):
        from aoep_shared.learner_adaptation import SensitivityRule
        adapt.sensitivity_rules = [
            SensitivityRule(**r) for r in req.adaptation["sensitivity_rules"]
        ]
    if adapt and req.adaptation.get("course_finishes"):
        from aoep_shared.learner_adaptation import CourseFinishRecord
        adapt.course_finishes = [
            CourseFinishRecord(**r) for r in req.adaptation["course_finishes"]
        ]
    state, base_plan = director.plan(ctx, signals)
    plan = merge_pacing_plan(
        signals,
        declared_pace=req.declared_pace,
        adaptation=adapt,
        class_type=req.class_type,
        course_complexity=req.course_complexity,
        wellness_state=req.wellness_state,
    )
    assert plan is not None
    return PlanResponse(
        next_state=state,
        pacing=plan.pacing,
        difficulty=plan.difficulty,
        reteach=plan.reteach,
        reasons=plan.reasons,
    )


class LxTickRequest(PlanRequest):
    frustration_events: int = 0


class LxTickResponse(BaseModel):
    lx_score: float
    lx_components: dict
    lx_target: float
    teaching_strategy: str
    improve_actions: list[str]
    pacing: Pacing
    difficulty: Difficulty
    reteach: bool
    reasons: list[str]
    next_state: LessonState


@app.post("/director/lx-tick", response_model=LxTickResponse)
def director_lx_tick(req: LxTickRequest) -> LxTickResponse:
    """Measure learning experience and return adaptations to improve the score."""
    from aoep_shared.learning_experience import LX_TARGET, lx_tick
    from aoep_shared.learner_adaptation import adaptation_from_dict

    director = Director()
    ctx = ClassContext(
        class_type=req.class_type,
        slides_total=req.slides_total,
        slide_index=req.slide_index,
        pending_questions=req.pending_questions,
        attention=req.attention,
        slides_since_quiz=req.slides_since_quiz,
    )
    signals = LearnerSignals(
        topic_mastery=req.topic_mastery,
        quiz_accuracy=req.quiz_accuracy,
        avg_response_latency_s=req.avg_response_latency_s,
        attention_trend=req.attention_trend,
        question_rate=req.question_rate,
    )
    adapt = adaptation_from_dict(req.adaptation) if req.adaptation else None
    if adapt and req.adaptation.get("failed_approaches"):
        from aoep_shared.learner_adaptation import FailedApproach
        adapt.failed_approaches = [
            FailedApproach(**f) for f in req.adaptation["failed_approaches"]
        ]
    if adapt and req.adaptation.get("sensitivity_rules"):
        from aoep_shared.learner_adaptation import SensitivityRule
        adapt.sensitivity_rules = [
            SensitivityRule(**r) for r in req.adaptation["sensitivity_rules"]
        ]
    bandit = (adapt.strategy_bandit if adapt else {}) or req.adaptation.get("strategy_bandit", {})
    result = lx_tick(
        signals=signals,
        slide_index=req.slide_index,
        slides_total=req.slides_total,
        class_type=req.class_type,
        declared_pace=req.declared_pace,
        adaptation=adapt,
        wellness_state=req.wellness_state,
        course_complexity=req.course_complexity,
        frustration_events=req.frustration_events,
        strategy_bandit=bandit,
    )
    state, _ = director.plan(ctx, signals)
    return LxTickResponse(
        lx_score=result.lx_score,
        lx_components=result.components.as_dict(),
        lx_target=LX_TARGET,
        teaching_strategy=result.teaching_strategy,
        improve_actions=result.improve_actions,
        pacing=result.pacing,
        difficulty=result.difficulty,
        reteach=result.reteach,
        reasons=result.reasons,
        next_state=state,
    )


# --------------------------------------------------------------------------- #
# Phase 5 - assessment (quizzes + grading)
# --------------------------------------------------------------------------- #
class QuizRequest(BaseModel):
    topic: str
    passages: list[str]
    max_items: int = 4
    # When student_id is set, difficulty adapts to the learner's mastery signals
    # (pulled from the memory service) instead of the static MEDIUM default.
    student_id: str | None = None
    class_type: ClassType = ClassType.GROUP


class QuizItemView(BaseModel):
    item_id: str
    topic: str
    prompt: str
    options: list[str]
    # answer_index is intentionally omitted — the correct answer is stored
    # server-side only and never sent to the client.
    difficulty: Difficulty


class QuizResponse(BaseModel):
    items: list[QuizItemView]


class GradeRequest(BaseModel):
    item_id: str
    chosen_index: int
    # answer_index is no longer accepted from the client — the correct answer
    # is looked up from the server-side quiz_items cache.
    topic: str = ""
    # When set, the outcome updates the learner's mastery in the memory service,
    # closing the loop so the next quiz adapts its difficulty.
    student_id: str | None = None


class GradeResponse(BaseModel):
    item_id: str
    correct: bool
    mastery_target: float
    difficulty: Difficulty


class PolicyAssessmentStartRequest(BaseModel):
    student_id: str
    session_id: str = ""
    course_id: str = ""
    checkpoint_id: str
    retention_check_id: str = ""
    stage: AssessmentStage = AssessmentStage.FORMATIVE
    profile_score: str = ""
    requested_format: str = "auto"
    device_mode: str = "class"
    needs_captions: bool = False
    uses_assistive_tech: bool = False
    max_items: int = 5

    model_config = {"extra": "forbid"}


class PolicyAssessmentSubmitRequest(BaseModel):
    chosen_indices: list[int]

    model_config = {"extra": "forbid"}


def _checkpoint_policy(
    checkpoint_id: str,
    stage: AssessmentStage,
) -> CheckpointPolicy:
    if stage == AssessmentStage.SUMMATIVE:
        return CheckpointPolicy(
            checkpoint_id=checkpoint_id,
            stage=stage,
            pass_threshold=0.7,
            min_items=4,
            max_attempts=3,
            ksb_coverage_min=0.6,
        )
    if stage == AssessmentStage.RETENTION:
        return CheckpointPolicy(
            checkpoint_id=checkpoint_id,
            stage=stage,
            pass_threshold=0.7,
            min_items=3,
            max_attempts=3,
        )
    return CheckpointPolicy(
        checkpoint_id=checkpoint_id,
        stage=stage,
        pass_threshold=0.6,
        min_items=2,
        max_attempts=10,
        required=False,
    )


def _assessment_ksb_maps(course_id: str, items: list[QuizItem]):
    ksb = get_sessions().curriculum.ksb_for(course_id)
    typed_codes: list[tuple[str, EvidenceDomain]] = []
    if ksb is not None:
        groups = [
            (ksb.knowledge, EvidenceDomain.KNOWLEDGE),
            (ksb.skills, EvidenceDomain.SKILL),
            (ksb.behaviours, EvidenceDomain.BEHAVIOUR),
        ]
        width = max((len(group) for group, _ in groups), default=0)
        for index in range(width):
            for group, domain in groups:
                if index < len(group):
                    typed_codes.append((group[index].code, domain))
    ksb_by_item: dict[str, list[str]] = {}
    domain_by_item: dict[str, EvidenceDomain] = {}
    for index, item in enumerate(items):
        if typed_codes:
            code, domain = typed_codes[index % len(typed_codes)]
            ksb_by_item[item.item_id] = [code]
            domain_by_item[item.item_id] = domain
        else:
            domain_by_item[item.item_id] = EvidenceDomain.KNOWLEDGE
    return ksb_by_item, domain_by_item


@app.get("/assessment/policy/{session_id}")
def assessment_policy_for_session(session_id: str) -> dict:
    """Return required assessment points for the current personalized lesson.

    Professional / corporate courses get a mid-course pop quiz plus a required
    end-of-course exam. Other audiences keep the denser 25/50/75% schedule.
    """
    sessions = get_sessions()
    try:
        lesson = sessions.lesson_for(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session")
    last = max(0, len(lesson.slides) - 1)
    audience = (getattr(lesson, "audience", None) or "general").lower()
    professional = audience in {"corporate", "professional", "enterprise"}

    if professional:
        mid = max(0, min(last, round(last * 0.5)))
        checkpoints = [
            {
                "checkpoint_id": "progress-mid",
                "stage": "formative",
                "after_slide_index": mid,
                "kind": "pop_quiz",
                "title": "Mid-course pop quiz",
            },
            {
                "checkpoint_id": "course-final",
                "stage": "summative",
                "after_slide_index": last,
                "kind": "final_exam",
                "title": "End-of-course assessment",
            },
        ]
        pass_rule = (
            "Professional courses require the mid-course pop quiz and a passing "
            "end-of-course assessment before completion credit."
        )
    else:
        checkpoints = [
            {
                "checkpoint_id": "progress-25",
                "stage": "formative",
                "after_slide_index": round(last * 0.25),
                "kind": "pop_quiz",
                "title": "Pop quiz · 25%",
            },
            {
                "checkpoint_id": "progress-50",
                "stage": "formative",
                "after_slide_index": round(last * 0.50),
                "kind": "pop_quiz",
                "title": "Pop quiz · 50%",
            },
            {
                "checkpoint_id": "progress-75",
                "stage": "formative",
                "after_slide_index": round(last * 0.75),
                "kind": "pop_quiz",
                "title": "Pop quiz · 75%",
            },
            {
                "checkpoint_id": "course-final",
                "stage": "summative",
                "after_slide_index": last,
                "kind": "final_exam",
                "title": "End-of-course assessment",
            },
        ]
        pass_rule = "passing summative assessment required"

    return {
        "session_id": session_id,
        "course_id": lesson.lesson_id,
        "audience": audience,
        "professional": professional,
        "checkpoints": checkpoints,
        "retention_intervals_days": [1, 7, 30, 90],
        "pass_rule": pass_rule,
    }


def _assessment_account_id(authorization: str) -> str:
    """Extract account id from a bearer token without calling identity."""
    from aoep_shared.auth import verify_token  # noqa: E402
    key = os.environ.get("AUTH_SIGNING_KEY", "dev-auth-signing-key").encode()
    bearer = (authorization or "").strip()
    if bearer.lower().startswith("bearer "):
        bearer = bearer[7:].strip()
    claims = verify_token(bearer, key) if bearer else None
    return str(claims.get("sub", "")).strip() if claims else ""


def _identity_profile_from_auth(authorization: str):
    """Return (account_id, profile_ns) where profile_ns has display_name and email.

    Decodes the bearer token locally — same key as _assessment_account_id — and
    exposes the name/email claims so callers can build a human-readable label
    without a network round-trip to an identity service.
    """
    from aoep_shared.auth import verify_token  # noqa: E402
    key = os.environ.get("AUTH_SIGNING_KEY", "dev-auth-signing-key").encode()
    bearer = (authorization or "").strip()
    if bearer.lower().startswith("bearer "):
        bearer = bearer[7:].strip()
    claims = verify_token(bearer, key) if bearer else {}

    class _ProfileNS:
        display_name: str = claims.get("name") or claims.get("display_name") or ""  # type: ignore[assignment]
        email: str = claims.get("email") or ""  # type: ignore[assignment]

    return str(claims.get("sub", "")).strip(), _ProfileNS()


@app.post("/assessment/checkpoints/start")
def assessment_checkpoint_start(
    req: PolicyAssessmentStartRequest,
    authorization: str = Header(default=""),
) -> dict:
    """Create a private answer-key run and return a profile-selected presentation."""
    account_id = _assessment_account_id(authorization)
    if not account_id:
        raise HTTPException(status_code=401, detail="authentication required for assessments")
    sessions = get_sessions()
    session = None
    course_id = req.course_id.strip()
    if req.session_id:
        try:
            session = sessions.get_session(req.session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown session")
        course_id = session.lesson_id
    lesson = sessions.curriculum.get(course_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail=f"unknown course {course_id}")
    if req.stage == AssessmentStage.SUMMATIVE:
        if session is None:
            raise HTTPException(status_code=422, detail="summative assessment requires a session")
        planned = sessions.lesson_for(session.session_id)
        if session.current_slide < len(planned.slides) - 1:
            raise HTTPException(status_code=409, detail="course-final assessment is not due yet")
    if req.stage == AssessmentStage.RETENTION and not req.retention_check_id:
        raise HTTPException(status_code=422, detail="retention_check_id is required")

    policy = _checkpoint_policy(req.checkpoint_id, req.stage)
    max_items = max(policy.min_items, min(10, req.max_items))
    difficulty = Difficulty.MEDIUM
    if req.student_id:
        signals = sessions.memory.learner_signals(req.student_id, course_id)
        difficulty = AdaptivePolicy().plan(
            signals,
            class_type=ClassType(session.class_type) if session else ClassType.SOLO,
        ).difficulty
    items = definition_items_from_passages(
        sessions.curriculum.passages_for(course_id),
        course_id,
        max_items=max_items,
        difficulty=difficulty,
    )
    if len(items) < policy.min_items:
        raise HTTPException(status_code=422, detail="course has too little assessable content")
    try:
        presentation_format = select_assessment_format(
            req.profile_score,
            requested=req.requested_format,
            device_mode=req.device_mode,
            needs_captions=req.needs_captions,
            uses_assistive_tech=req.uses_assistive_tech,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # KNOWN_ISSUE: app.state.assessment_results is in-memory only. On service
    # restart all prior attempts are lost and attempt_number always starts at 1,
    # bypassing max_attempts. TODO: persist assessment_results to a durable store
    # (DB/Redis) to enforce the attempt limit correctly across restarts.
    _lock_key = f"{req.student_id}:{course_id}:{req.checkpoint_id}"
    with _assessment_lock_for(_lock_key):
        previous = [
            result for result in app.state.assessment_results
            if result.student_id == req.student_id
            and result.course_id == course_id
            and result.checkpoint_id == req.checkpoint_id
        ]
        attempt_number = len(previous) + 1
        if attempt_number > policy.max_attempts:
            raise HTTPException(status_code=409, detail="maximum checkpoint attempts exceeded")
        run_id = f"assess-{uuid.uuid4().hex[:16]}"
    ksb_by_item, domain_by_item = _assessment_ksb_maps(course_id, items)
    # Derive required_domains from the actual item mix for BOTH stages. The
    # class default ([KNOWLEDGE]) fails formative students who pass the score
    # threshold on skill/behaviour items but miss the knowledge items — the
    # requirement must match what the checkpoint actually asks.
    policy.required_domains = sorted(
        set(domain_by_item.values()),
        key=lambda domain: domain.value,
    )
    app.state.assessment_runs[run_id] = {
        "student_id": req.student_id,
        "account_id": account_id,
        "course_id": course_id,
        "policy": policy,
        "items": items,
        "presentation_format": presentation_format,
        "attempt_number": attempt_number,
        "ksb_by_item": ksb_by_item,
        "domain_by_item": domain_by_item,
        "retention_check_id": req.retention_check_id,
    }
    return {
        "run_id": run_id,
        "student_id": req.student_id,
        "course_id": course_id,
        "checkpoint": policy.model_dump(mode="json"),
        "attempt_number": attempt_number,
        "presentation_format": presentation_format.value,
        "items": [present_item(item, presentation_format) for item in items],
        "answer_key_exposed": False,
    }


def _assessment_signing_key() -> bytes:
    return os.environ.get(
        "ASSESSMENT_SIGNING_KEY",
        os.environ.get("AUTH_SIGNING_KEY", "dev-assessment-signing-key"),
    ).encode()


@app.post("/assessment/checkpoints/{run_id}/submit")
def assessment_checkpoint_submit(
    run_id: str,
    req: PolicyAssessmentSubmitRequest,
    authorization: str = Header(default=""),
) -> dict:
    """Grade against the server-held key and issue a signed pass decision."""
    account_id = _assessment_account_id(authorization)
    if not account_id:
        raise HTTPException(status_code=401, detail="authentication required for assessments")
    run = app.state.assessment_runs.pop(run_id, None)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown or already submitted assessment run")
    if run.get("account_id") and run["account_id"] != account_id:
        # Put the run back so it isn't consumed by an impersonator.
        app.state.assessment_runs[run_id] = run
        raise HTTPException(status_code=403, detail="assessment run belongs to another account")
    try:
        result = evaluate_checkpoint(
            student_id=run["student_id"],
            course_id=run["course_id"],
            policy=run["policy"],
            items=run["items"],
            chosen_indices=req.chosen_indices,
            presentation_format=run["presentation_format"],
            attempt_number=run["attempt_number"],
            ksb_by_item=run["ksb_by_item"],
            domain_by_item=run["domain_by_item"],
        )
    except ValueError as exc:
        # Put the run back: a malformed submission (e.g. wrong answer count)
        # must not destroy the in-progress exam — no attempt was consumed.
        app.state.assessment_runs[run_id] = run
        raise HTTPException(status_code=422, detail=str(exc))
    _submit_lock_key = f"{run['student_id']}:{run['course_id']}:{run['policy'].checkpoint_id}"
    with _assessment_lock_for(_submit_lock_key):
        app.state.assessment_results.append(result)
    memory = get_sessions().memory
    for evidence in result.item_evidence:
        memory.record_behavior(
            result.student_id,
            result.course_id,
            quiz_correct=evidence.correct,
        )
        memory.update_mastery(result.student_id, result.course_id, evidence.correct)

    from aoep_shared.auth import sign_token

    evidenced_codes = sorted({
        code
        for evidence in result.item_evidence
        if evidence.correct
        for code in evidence.ksb_codes
    })
    response = {
        "attempt": result.model_dump(mode="json"),
        "course_decision": None,
        "attempt_result_token": sign_token(
            {
                "kind": "assessment_attempt",
                "student_id": result.student_id,
                "course_id": result.course_id,
                "checkpoint_id": result.checkpoint_id,
                "stage": result.stage.value,
                "attempt_id": result.attempt_id,
                "score": result.score,
                "passed": result.passed,
                "presentation_format": result.presentation_format.value,
                "ksb_codes": evidenced_codes,
            },
            _assessment_signing_key(),
            ttl_s=3_600,
        ),
    }
    if result.stage == AssessmentStage.SUMMATIVE:
        decision = decide_course_pass(
            result.student_id,
            result.course_id,
            app.state.assessment_results,
        )
        response["course_decision"] = decision.model_dump(mode="json")
        if decision.passed:
            response["pass_decision_token"] = sign_token(
                {
                    "kind": "assessment_pass",
                    "student_id": decision.student_id,
                    "course_id": decision.course_id,
                    "score": decision.score,
                    "attempt_ids": decision.attempt_ids,
                    "ksb_codes": decision.ksb_codes_evidenced,
                },
                _assessment_signing_key(),
                ttl_s=3_600,
            )
    elif result.stage == AssessmentStage.RETENTION:
        response["retention_result_token"] = sign_token(
            {
                "kind": "retention_result",
                "student_id": result.student_id,
                "course_id": result.course_id,
                "check_id": run["retention_check_id"],
                "attempt_id": result.attempt_id,
                "score": result.score,
                "passed": result.passed,
            },
            _assessment_signing_key(),
            ttl_s=3_600,
        )
    return response


@app.post("/assessment/quiz", response_model=QuizResponse)
def assessment_quiz(req: QuizRequest) -> QuizResponse:
    # Adapt difficulty to the learner when we know who they are; otherwise keep
    # the static MEDIUM default (unchanged behavior for anonymous callers).
    difficulty = Difficulty.MEDIUM
    if req.student_id:
        signals = get_sessions().memory.learner_signals(req.student_id, req.topic)
        difficulty = AdaptivePolicy().plan(signals, class_type=req.class_type).difficulty
    items = definition_items_from_passages(
        req.passages, req.topic, max_items=req.max_items, difficulty=difficulty
    )
    # Cache items server-side so the correct answer is never exposed to the client.
    # Apply a simple size cap to prevent unbounded memory growth.
    quiz_cache: dict = app.state.quiz_items
    if len(quiz_cache) > 50_000:
        quiz_cache.clear()
    for i in items:
        quiz_cache[i.item_id] = i
    return QuizResponse(
        items=[
            QuizItemView(
                item_id=i.item_id,
                topic=i.topic,
                prompt=i.prompt,
                options=i.options,
                difficulty=i.difficulty,
            )
            for i in items
        ]
    )


@app.post("/assessment/grade", response_model=GradeResponse)
def assessment_grade(req: GradeRequest) -> GradeResponse:
    # Look up the quiz item from the server-side cache; never trust client-supplied
    # answer indices (Bug 4 fix).
    stored_item: QuizItem | None = app.state.quiz_items.get(req.item_id)
    if stored_item is None:
        raise HTTPException(status_code=404, detail="unknown quiz item; start a new quiz")
    item = stored_item
    result: GradeResult = grade(item, req.chosen_index)
    # Close the adaptive loop: persist the outcome so the learner's mastery (BKT)
    # updates and the next quiz personalizes. Best-effort; skipped when anonymous.
    if req.student_id and req.topic:
        memory = get_sessions().memory
        memory.record_behavior(req.student_id, req.topic, quiz_correct=result.correct)
        memory.update_mastery(req.student_id, req.topic, result.correct)
    return GradeResponse(
        item_id=result.item_id,
        correct=result.correct,
        mastery_target=result.mastery_target,
        difficulty=result.difficulty,
    )


# --------------------------------------------------------------------------- #
# Scheduled group classes (the AI drives the coursework through Zoom / Teams /
# Google Meet, or the built-in Salareen room). Educators schedule a lesson on a
# platform at a time; learners browse the schedule and register. ``start`` spins
# up the teaching session and returns the bridge plan that pipes the AI's
# LiveKit room into the external meeting so it presents through that platform.
# --------------------------------------------------------------------------- #
from aoep_shared.group_classes import (  # noqa: E402
    AUDIT_PENDING,
    ClassFullError,
    GroupClassError,
    GroupClassStore,
    PAYMENT_PAID,
    PAYMENT_PENDING,
    bridge_plan,
)
from aoep_shared.live_room import (  # noqa: E402
    AI_HOST_ID,
    BannedError,
    LiveRoomError,
    LiveRoomStore,
    RateLimitedError,
    RoomFullError,
)

app.state.group_classes = GroupClassStore()
app.state.live_rooms = LiveRoomStore()

from aoep_shared.live_room_ws import ws_host_delta, ws_room_snapshot  # noqa: E402

from .live_room_hub import LiveRoomConnectionHub  # noqa: E402

app.state.live_room_hub = LiveRoomConnectionHub()


def _seed_group_classes() -> None:
    from aoep_shared.group_classes import ensure_standard_daily_classes

    try:
        n = ensure_standard_daily_classes(_group_store())
        if n:
            import logging
            logging.getLogger(__name__).info("seeded %d standard group classes", n)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("group class seed skipped (%s)", exc)


def _cleanup_expired_classes() -> int:
    """Delete group classes whose allotted time has fully finished, and end any
    matching live room so it stops being joinable. Runs on a 60s cron (below) and
    lazily on every listing, so a past class is removed within a minute even if
    nobody loads the page."""
    import logging
    from datetime import datetime, timezone

    store = _group_store()
    ref = datetime.now(timezone.utc)
    # End the live room of any class about to be purged (best-effort).
    for c in list(store.list(upcoming_only=False, include_ended=True, now=ref)):
        end = c.start_dt.timestamp() + c.duration_min * 60
        if end < ref.timestamp() and c.live_room_id:
            try:
                if _live_rooms().get(c.live_room_id) is not None:
                    _live_rooms().end_room(c.live_room_id, auto=True)
            except Exception:  # noqa: BLE001
                logging.getLogger(__name__).debug("room end skipped for %s", c.id, exc_info=True)
    removed = store.purge_expired(now=ref)
    if removed:
        logging.getLogger(__name__).info("cleaned up %d expired group classes", removed)
    return removed


async def _class_cleanup_loop() -> None:
    """Every 60 seconds, purge classes whose time is over (the cleanup cron)."""
    import asyncio
    import logging

    while True:
        try:
            await asyncio.sleep(60)
            _cleanup_expired_classes()
        except asyncio.CancelledError:  # graceful shutdown
            raise
        except Exception:  # noqa: BLE001 - a cleanup hiccup must never crash the loop
            logging.getLogger(__name__).debug("class cleanup tick failed", exc_info=True)


@app.on_event("startup")
async def _orchestrator_startup() -> None:
    import asyncio
    import logging as _log

    # Capture the running loop so background threads (e.g. the streamed AI-host
    # answer, which runs a blocking LLM generator in a threadpool) can push
    # WebSocket frames back onto it via run_coroutine_threadsafe.
    app.state.loop = asyncio.get_running_loop()
    _seed_group_classes()
    _cleanup_expired_classes()  # sweep once at boot
    app.state._class_cleanup_task = asyncio.create_task(_class_cleanup_loop())

    _lg = _log.getLogger(__name__)
    _orch_key = os.environ.get("ASSESSMENT_SIGNING_KEY") or os.environ.get("AUTH_SIGNING_KEY")
    if not _orch_key:
        _lg.warning(
            "Neither ASSESSMENT_SIGNING_KEY nor AUTH_SIGNING_KEY is set on the orchestrator. "
            "Assessment tokens will be signed with the insecure development default key."
        )
    elif not os.environ.get("ASSESSMENT_SIGNING_KEY") and os.environ.get("AUTH_SIGNING_KEY"):
        _lg.info(
            "ASSESSMENT_SIGNING_KEY not set — orchestrator will sign assessment tokens "
            "with AUTH_SIGNING_KEY. Ensure the identity service uses the same key."
        )


def _group_store() -> GroupClassStore:
    return app.state.group_classes


# Maps checkout_session_id -> voucher_code for pending paid checkouts.
# Consumed in confirm_group_class_payment once payment is verified.
_pending_vouchers: dict[str, str] = {}


def _live_rooms() -> LiveRoomStore:
    return app.state.live_rooms


def _group_class_payload(gc) -> dict:
    payload = gc.to_dict()
    stats = _group_store().instructor_stats(gc.instructor_account_id)
    payload["instructor_stats"] = stats
    return payload


def _human_taught_kwargs(gc) -> dict:
    """Room kwargs marking a class as taught by a person rather than Theodore.

    A class scheduled by an instructor (as opposed to a student study group, which
    only carries created_by_account_id) is human-taught: the instructor presents,
    so no AI host is placed in the room.
    """
    instructor_account = (getattr(gc, "instructor_account_id", "") or "").strip()
    if not getattr(gc, "human_taught", False) or not instructor_account:
        return {}
    return {
        "human_taught": True,
        "human_host_account_id": instructor_account,
        "human_host_name": (
            (getattr(gc, "instructor_name", "") or "").strip()
            or (getattr(gc, "host", "") or "").strip()
            or "Instructor"
        ),
    }


def _class_host_is_caller(gc, authorization: str) -> bool:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    caller = account_from_authorization(authorization) or ""
    if not caller:
        return False
    return caller in gc.host_account_ids


def _group_class_for_room(room_id: str):
    if not room_id.startswith("class-"):
        return None
    return _find_group_class(room_id[len("class-"):])


def _require_host_can_teach(gc) -> None:
    if not gc.host_account_ids:
        return
    if not gc.can_start_teaching():
        raise LiveRoomError(
            "Check in at least 5 minutes before the scheduled start to teach a paid class. "
            "With no paying students you can still run a practice session."
        )


async def _broadcast_live_room(room_id: str, event: dict) -> None:
    await app.state.live_room_hub.broadcast(room_id, event)


def _schedule_live_broadcast(background: BackgroundTasks, room_id: str, event: dict) -> None:
    background.add_task(_broadcast_live_room, room_id, event)


def _broadcast_threadsafe(room_id: str, event: dict) -> None:
    """Broadcast a live-room WS event from a worker thread (e.g. the streamed
    AI-host answer generator runs in Starlette's threadpool). Schedules the async
    broadcast on the captured event loop; never raises into the caller."""
    import asyncio

    loop = getattr(app.state, "loop", None)
    if loop is None or loop.is_closed() or not loop.is_running():
        return
    coro = app.state.live_room_hub.broadcast(room_id, event)
    try:
        asyncio.run_coroutine_threadsafe(coro, loop)
    except Exception:  # noqa: BLE001 - a WS hiccup must never break the answer stream
        coro.close()


class ScheduleGroupClassRequest(BaseModel):
    title: str
    lesson_id: str
    start_time: str
    platform: str = "salareen"
    meeting_url: str = ""
    duration_min: int = 60
    host: str = "Salareen AI"
    capacity: int = 100
    room_size: int = 6
    language: str = "en"
    audience: str = "general"
    description: str = ""
    marketplace_listing: bool = False
    audit_required: bool = False
    credentials_summary: str = ""
    credential_photo_url: str = ""
    identity_photo_url: str = ""
    interview_notes: str = ""
    demo_notes: str = ""
    instructor_name: str = ""
    price_per_user_usd: float = 0.0
    commission_rate: float = 0.15
    payment_required: bool = False
    attendee_code_required: bool = False
    presentation_filename: str = ""
    max_faces_allowed: int = 1
    require_liveness: bool = True
    recording_protection_required: bool = True
    device_profile: str = ""
    camera_ingest_mode: str = "platform_default"
    camera_sources: list[dict] = []
    is_student_session: bool = False  # True when a student self-schedules a study group


class RegisterRequest(BaseModel):
    name: str
    email: str = ""
    checkout_session_id: str = ""
    payment_status: str = "unpaid"
    attendee_code: str = ""


class GroupClassCheckoutRequest(BaseModel):
    name: str
    email: str = ""
    payment_method: str = "card"   # card | apple_pay | google_pay | paypal | venmo | zelle | cashapp | klarna | afterpay | voucher
    voucher_code: str = ""         # optional discount/gift/free-pass code


class GroupClassConfirmPaymentRequest(BaseModel):
    checkout_session_id: str


class GroupClassReviewRequest(BaseModel):
    rating: int
    comment: str = ""


class GroupClassAuditRequest(BaseModel):
    approved: bool
    interview_notes: str = ""
    demo_notes: str = ""


class GroupClassCameraSourcesRequest(BaseModel):
    device_profile: str = ""
    camera_ingest_mode: str = ""
    camera_sources: list[dict] = []


class TeachRequest(BaseModel):
    title: str
    lesson_id: str
    start_time: str
    duration_min: int = 60
    language: str = "en"
    description: str = ""
    instructor_name: str = ""
    credentials_summary: str
    credential_photo_url: str = ""
    identity_photo_url: str = ""
    demo_notes: str = ""
    interview_notes: str = ""
    price_per_user_usd: float = 0.0
    capacity: int = 8
    room_size: int = 9
    commission_rate: float = 0.15
    max_faces_allowed: int = 1
    require_liveness: bool = True
    recording_protection_required: bool = True
    device_profile: str = "teams_cisco_room"
    camera_ingest_mode: str = "external_preferred"
    camera_sources: list[dict] = []


class LiveRoomLocation(BaseModel):
    """Client-reported geo for room discovery (Bigo-style browse)."""
    country: str = ""
    state: str = ""
    city: str = ""
    latitude: float = 0.0
    longitude: float = 0.0


@app.get("/api/group-classes")
def list_group_classes(upcoming: bool = True) -> dict:
    from aoep_shared.group_classes import ensure_standard_daily_classes

    ensure_standard_daily_classes(_group_store())
    classes = _group_store().list(upcoming_only=upcoming)
    return {"classes": [_group_class_payload(c) for c in classes]}


@app.post("/api/group-classes")
def schedule_group_class(
    req: ScheduleGroupClassRequest,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    payload = req.model_dump()
    payload.pop("is_student_session", None)  # not a GroupClass field
    payload["created_by_account_id"] = account_id
    if account_id and not req.is_student_session:
        payload["instructor_account_id"] = account_id
        payload["created_by_account_id"] = account_id
        # A signed-in user scheduling a non-student session is teaching it.
        payload["human_taught"] = True
        # Label it with the person's name: the "Salareen AI" default would claim an
        # AI teaches a class that a human actually teaches.
        from aoep_shared.live_room_rewards import display_name_from_authorization

        teacher_name = (payload.get("instructor_name") or "").strip() or (
            display_name_from_authorization(authorization) or ""
        )
        if teacher_name:
            payload["instructor_name"] = teacher_name
            if not (req.host or "").strip() or req.host == "Salareen AI":
                payload["host"] = teacher_name
    if req.marketplace_listing:
        payload["instructor_account_id"] = account_id
        payload["audit_required"] = True
        payload["audit_status"] = AUDIT_PENDING
    try:
        gc = _group_store().schedule(**payload)
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _group_class_payload(gc)


@app.post("/api/group-classes/upload-presentation")
async def upload_host_presentation(
    file: UploadFile = File(...),
    title: str = Form(""),
    language: str = Form("en"),
    authorization: str = Header(default=""),
) -> dict:
    """Convert a host PDF/PPTX into a lesson the live class can page through."""
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    from .host_presentation import import_presentation_bytes

    account_id = account_from_authorization(authorization) or ""
    if not account_id:
        raise HTTPException(status_code=401, detail="sign in required to upload a presentation")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="presentation file is empty")
    sessions = get_sessions()
    try:
        lesson_id, lesson, filename = import_presentation_bytes(
            data,
            filename=file.filename or "presentation.pdf",
            title=title,
            language=language,
            store=sessions.curriculum,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"could not import presentation: {exc}")
    return {
        "lesson_id": lesson_id,
        "title": lesson.title,
        "slide_count": len(lesson.slides),
        "presentation_filename": filename,
    }


def _find_unique_group_class_prefix(store: GroupClassStore, class_id: str):
    if len(class_id) < 8:
        return None
    matches = [gc for gc in store.list(upcoming_only=False) if gc.id.startswith(class_id)]
    if len(matches) == 1:
        return matches[0]
    return None


def _find_group_class(class_id: str):
    """Look up a class, materializing the standard (deterministic-id) classes on
    a miss. On multi-replica / post-restart deployments the class listed by one
    replica may not yet exist in this worker's store; seeding is idempotent and
    reproduces the same ids, so the retry finds it. Legacy live-room links used
    class id prefixes in room ids, so a unique prefix is accepted as well."""
    store = _group_store()
    gc = store.get(class_id)
    if gc is None:
        _seed_group_classes()
        gc = store.get(class_id)
        if gc is None:
            gc = _find_unique_group_class_prefix(store, class_id)
    return gc


@app.get("/api/group-classes/{class_id}")
def get_group_class(class_id: str) -> dict:
    gc = _find_group_class(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")
    return _group_class_payload(gc)


@app.post("/api/group-classes/{class_id}/register")
def register_group_class(
    class_id: str,
    req: RegisterRequest,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    store = _group_store()
    account_id = account_from_authorization(authorization) or ""
    if store.get(class_id) is None:
        _seed_group_classes()   # materialize standard classes on a miss (see _find_group_class)
    try:
        if req.attendee_code.strip():
            store.authorize_attendee(
                class_id,
                attendee_code=req.attendee_code,
                account_id=account_id,
                identity="",
            )
        store.register(
            class_id,
            req.name,
            req.email,
            account_id=account_id,
            checkout_session_id=req.checkout_session_id,
            payment_status=req.payment_status,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown group class")
    except ClassFullError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _group_class_payload(store.require(class_id))


@app.post("/api/group-classes/{class_id}/camera-sources")
def upsert_group_class_camera_sources(
    class_id: str,
    req: GroupClassCameraSourcesRequest,
    authorization: str = Header(default=""),
) -> dict:
    gc = _find_group_class(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")
    if not (_request_is_admin(authorization) or _class_host_is_caller(gc, authorization)):
        raise HTTPException(status_code=403, detail="class host or admin required")
    if req.device_profile.strip():
        gc.device_profile = req.device_profile.strip().lower()
    if req.camera_ingest_mode.strip():
        gc.camera_ingest_mode = req.camera_ingest_mode.strip().lower()
    gc.camera_sources = [
        dict(row) for row in req.camera_sources if isinstance(row, dict)
    ][:16]
    _group_store().save(gc)
    return _group_class_payload(gc)


@app.post("/api/group-classes/teach-request")
def submit_teach_request(
    req: TeachRequest,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    if not account_id:
        raise HTTPException(status_code=401, detail="sign in required to request teaching")
    payload = {
        "title": req.title,
        "lesson_id": req.lesson_id,
        "start_time": req.start_time,
        "duration_min": req.duration_min,
        "language": req.language,
        "description": req.description,
        "host": req.instructor_name or "Instructor",
        "instructor_name": req.instructor_name or "Instructor",
        "capacity": req.capacity,
        "room_size": req.room_size,
        "marketplace_listing": True,
        "audit_required": True,
        "audit_status": AUDIT_PENDING,
        "created_by_account_id": account_id,
        "instructor_account_id": account_id,
        "credentials_summary": req.credentials_summary,
        "credential_photo_url": req.credential_photo_url,
        "identity_photo_url": req.identity_photo_url,
        "interview_notes": req.interview_notes,
        "demo_notes": req.demo_notes,
        "price_per_user_usd": req.price_per_user_usd,
        "commission_rate": req.commission_rate,
        "payment_required": True,
        "attendee_code_required": True,
        "max_faces_allowed": req.max_faces_allowed,
        "require_liveness": req.require_liveness,
        "recording_protection_required": req.recording_protection_required,
        "device_profile": req.device_profile,
        "camera_ingest_mode": req.camera_ingest_mode,
        "camera_sources": req.camera_sources,
    }
    try:
        gc = _group_store().schedule(**payload)
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _group_class_payload(gc)


@app.post("/api/group-classes/{class_id}/audit")
def audit_group_class(
    class_id: str,
    req: GroupClassAuditRequest,
    authorization: str = Header(default=""),
) -> dict:
    if not _request_is_admin(authorization):
        raise HTTPException(status_code=403, detail="admin role required")
    try:
        gc = _group_store().audit_class(
            class_id,
            approved=req.approved,
            audited_by="salareen-employee",
            interview_notes=req.interview_notes,
            demo_notes=req.demo_notes,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown group class")
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _group_class_payload(gc)


@app.post("/api/group-classes/{class_id}/checkout")
def checkout_group_class(
    class_id: str,
    req: GroupClassCheckoutRequest,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    gc = _find_group_class(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")
    if gc.audit_required and gc.audit_status != "approved":
        raise HTTPException(status_code=400, detail="class has not yet passed Salareen audit")
    if gc.price_per_user_usd <= 0:
        raise HTTPException(status_code=400, detail="this class does not require paid checkout")

    # ── Voucher / promo code validation ──────────────────────────────────────
    import httpx as _httpx
    final_price = gc.price_per_user_usd
    voucher_desc = ""
    if req.voucher_code.strip():
        try:
            vresp = _httpx.post(
                f"{os.environ.get('IDENTITY_URL', 'http://identity:8000')}/vouchers/validate",
                json={"code": req.voucher_code.strip(), "price_usd": gc.price_per_user_usd, "class_id": class_id},
                headers={"Authorization": authorization},
                timeout=5,
            )
            if vresp.status_code == 200:
                vdata = vresp.json()
                if vdata.get("valid"):
                    final_price = vdata["final_price"]
                    voucher_desc = vdata["description"]
                else:
                    raise HTTPException(status_code=400, detail=vdata.get("error", "invalid voucher"))
        except _httpx.RequestError:
            pass  # identity service unavailable — skip voucher, continue with full price

    # ── Free pass: voucher covers full cost, skip payment provider ──────────
    if final_price == 0:
        try:
            free_session_id = f"voucher-{uuid.uuid4().hex[:8]}"
            reg = _group_store().open_checkout(
                class_id,
                name=req.name,
                email=req.email,
                account_id=account_id,
                checkout_session_id=free_session_id,
            )
            _group_store().confirm_checkout(
                class_id,
                checkout_session_id=free_session_id,
                account_id=account_id,
            )
            # Consume the voucher so max_uses is enforced
            if req.voucher_code.strip():
                try:
                    import httpx as _httpx_vc
                    _httpx_vc.post(
                        f"{os.environ.get('IDENTITY_URL', 'http://identity:8000')}/vouchers/consume",
                        json={"code": req.voucher_code.strip()},
                        headers={"X-Internal-Token": os.environ.get("INTERNAL_SECRET", "")},
                        timeout=3,
                    )
                except Exception:
                    pass  # best-effort; do not block the user
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown group class")
        except ClassFullError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except GroupClassError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "checkout": {
                "session_id": free_session_id,
                "url": "",
                "provider": "voucher",
                "method": "voucher",
                "payment_status": PAYMENT_PAID,
                "voucher_description": voucher_desc,
            },
            "registration": reg.__dict__,
            "free": True,
        }

    payment = app.state.factory.payment()
    customer_id = account_id or req.email.strip() or req.name.strip().lower().replace(" ", "-")
    plan_name = f"class-{gc.id}"
    try:
        session = payment.create_checkout(customer_id=customer_id, plan=plan_name)
        reg = _group_store().open_checkout(
            class_id,
            name=req.name,
            email=req.email,
            account_id=account_id,
            checkout_session_id=session.session_id,
        )
        if req.voucher_code.strip():
            _pending_vouchers[session.session_id] = req.voucher_code.strip()
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown group class")
    except ClassFullError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (ValueError, NotImplementedError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "checkout": {
            "session_id": session.session_id,
            "url": session.url,
            "provider": session.provider,
            "method": req.payment_method,
            "payment_status": PAYMENT_PENDING,
            "voucher_description": voucher_desc,
        },
        "registration": reg.__dict__,
    }


@app.post("/api/group-classes/{class_id}/confirm-payment")
def confirm_group_class_payment(
    class_id: str,
    req: GroupClassConfirmPaymentRequest,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    if not account_id:
        raise HTTPException(status_code=401, detail="authentication required to confirm payment")
    # Verify payment status with the payment provider before granting access.
    try:
        provider = app.state.factory.payment()
        status = provider.get_checkout_status(req.checkout_session_id)
        if status != "paid":
            raise HTTPException(status_code=402, detail=f"Payment not complete (status: {status})")
    except NotImplementedError:
        pass  # SandboxPaymentProvider in dev/test — allow
    try:
        reg = _group_store().confirm_checkout(
            class_id,
            checkout_session_id=req.checkout_session_id,
            account_id=account_id,
        )
        gc = _group_store().require(class_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown group class")
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Consume any pending voucher associated with this checkout session
    pending_code = _pending_vouchers.pop(req.checkout_session_id, "")
    if pending_code:
        try:
            import httpx as _httpx_vc
            _httpx_vc.post(
                f"{os.environ.get('IDENTITY_URL', 'http://identity:8000')}/vouchers/consume",
                json={"code": pending_code},
                headers={"X-Internal-Token": os.environ.get("INTERNAL_SECRET", "")},
                timeout=3,
            )
        except Exception:
            pass  # best-effort; do not block the user
    return {
        "class": _group_class_payload(gc),
        "registration": reg.__dict__,
        "attendee_code": reg.attendee_code,
        "payment_status": PAYMENT_PAID,
    }


@app.post("/api/group-classes/{class_id}/review")
def review_group_class(
    class_id: str,
    req: GroupClassReviewRequest,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    reviewer_name = "Learner"
    if account_id:
        try:
            _, acct = _identity_profile_from_auth(authorization)
            reviewer_name = acct.display_name or acct.email or reviewer_name
        except Exception:
            reviewer_name = "Learner"
    try:
        review = _group_store().add_review(
            class_id,
            reviewer_name=reviewer_name,
            rating=req.rating,
            comment=req.comment,
            reviewer_account_id=account_id,
        )
        gc = _group_store().require(class_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown group class")
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"class": _group_class_payload(gc), "review": review.to_dict()}


@app.get("/api/group-classes/{class_id}/calendar.ics")
def group_class_calendar(class_id: str, name: str = "", email: str = "") -> Response:
    from aoep_shared.group_classes import calendar_ics

    gc = _group_store().get(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")
    body = calendar_ics(gc, attendee_name=name, attendee_email=email)
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="salareen-{class_id}.ics"'},
    )


@app.post("/api/group-classes/{class_id}/start")
def start_group_class(
    class_id: str,
    req: LiveRoomLocation = LiveRoomLocation(),
    authorization: str = Header(default=""),
) -> dict:  # noqa: F811 (overrides nothing)
    """Go live: create the teaching session and return the meeting bridge plan.

    The AI's coursework runs as a normal teaching session; the returned
    ``bridge`` describes how to pipe its LiveKit room into the scheduled
    meeting (Zoom/Teams/Meet) so the AI presents through that platform. For
    built-in "salareen" classes, learners join the live room directly.
    """
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    store = _group_store()
    gc = _find_group_class(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")
    if gc.audit_required and gc.audit_status != "approved":
        raise HTTPException(status_code=400, detail="class is pending Salareen audit approval")
    account_id = account_from_authorization(authorization) or ""
    if gc.host_account_ids and not (_class_host_is_caller(gc, authorization) or _request_is_admin(authorization)):
        raise HTTPException(status_code=403, detail="only the scheduled host can start this class")
    if account_id:
        gc.record_host_checkin(account_id)
        store.save(gc)

    sessions = get_sessions()
    # If the class is already live, return the existing session so the host can
    # reconnect after closing or navigating away — don't create a duplicate session.
    if gc.status == "live" and gc.session_id and gc.live_room_id:
        existing = sessions.get_session(gc.session_id) if hasattr(sessions, 'get_session') else None
        if existing:
            room = gc.live_room_id
            plan = dict(bridge_plan(gc, livekit_room=room))
            live_room = _live_rooms().get(room)
            moderator_key = live_room.moderator_key if live_room else ""
            if moderator_key:
                plan["moderator_key"] = moderator_key
            media = app.state.factory.media()
            token = media.issue_token(room=room, identity="aoep-teacher")
            plan["livekit"] = {"room": token.room, "token": token.token, "url": token.url}
            return {
                "class": _group_class_payload(gc),
                "session": SessionView(
                    session=existing,
                    lesson=sessions.lesson_for(existing.session_id),
                    slide=sessions.current_slide(existing.session_id),
                ).model_dump(),
                "bridge": plan,
            }
    try:
        state = sessions.start_session(gc.lesson_id, "group")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {gc.lesson_id}")

    gc.session_id = state.session_id
    gc.status = "live"

    room = f"class-{gc.id}"
    slide = sessions.current_slide(state.session_id)
    moderator_key = ""
    if gc.platform == "salareen":
        gc.live_room_id = room
        live = _live_rooms().open_room(
            room_id=room,
            class_id=gc.id,
            session_id=state.session_id,
            lesson_id=gc.lesson_id,
            title=gc.title,
            room_size=gc.room_size,
            slide_title=slide.title,
            slide_body=slide.body,
            slide_narration=slide.narration,
            country=req.country,
            state=req.state,
            city=req.city,
            latitude=req.latitude,
            longitude=req.longitude,
            creator_name=gc.host or "Salareen",
            creator_account_id=gc.instructor_account_id or gc.created_by_account_id,
            **_human_taught_kwargs(gc),
            scheduled_start=gc.start_time,
            duration_seconds=int(gc.duration_min) * 60,
            presence_enabled=True,
            presence_hold_grace_seconds=90,
            presence_stale_seconds=20,
            presence_require_liveness=bool(gc.require_liveness),
            presence_max_faces_allowed=int(gc.max_faces_allowed or 1),
        )
        moderator_key = live.moderator_key

    store.save(gc)

    plan = dict(bridge_plan(gc, livekit_room=room))
    if moderator_key:
        plan["moderator_key"] = moderator_key
    media = app.state.factory.media()
    token = media.issue_token(room=room, identity="aoep-teacher")
    plan["livekit"] = {"room": token.room, "token": token.token, "url": token.url}

    return {
        "class": _group_class_payload(gc),
        "session": SessionView(
            session=state,
            lesson=sessions.lesson_for(state.session_id),
            slide=sessions.current_slide(state.session_id),
        ).model_dump(),
        "bridge": plan,
    }


# --------------------------------------------------------------------------- #
# Salareen Live Room (built-in multi-user grid for group classes)
# --------------------------------------------------------------------------- #


class LiveRoomJoinRequest(BaseModel):
    name: str
    identity: str = ""
    attendee_code: str = ""
    language: str = ""
    student_id: str = ""
    readiness_score: float = 0.0
    readiness_band: str = ""
    primary_style: str = ""


class LiveRoomPresenceReportRequest(BaseModel):
    participant_id: str
    present: bool = False
    face_count: int = 0
    liveness_state: str = "unknown"
    liveness_score: float = 0.0
    reason: str = ""
    source: str = "client"
    observed_at: str = ""


class XrLabEnableRequest(BaseModel):
    moderator_key: str = ""
    participant_id: str = ""
    lesson_id: str = ""
    course_id: str = ""
    title: str = ""
    enabled: bool = True


class XrObservationItem(BaseModel):
    seq: int = 0
    action: str
    target_id: str = ""
    hand: str = ""
    confidence: float = 1.0
    hold_ms: int = 0
    ts_ms: int = 0
    pose: dict = {}


class XrCompleteRequest(BaseModel):
    participant_id: str
    student_id: str = ""
    client_kind: str = "webxr"
    observations: list[XrObservationItem] = []
    lab_id: str = ""


class LiveRoomChatRequest(BaseModel):
    participant_id: str
    text: str


class LiveRoomMuteRequest(BaseModel):
    participant_id: str
    muted: bool
    by_host: bool = False
    actor_id: str = ""
    moderator_key: str = ""


class LiveRoomHandRequest(BaseModel):
    participant_id: str
    question: str = ""


class LiveRoomQueueRequest(BaseModel):
    participant_id: str
    question: str = ""


class LiveRoomTurnRequest(BaseModel):
    participant_id: str = ""
    moderator_key: str = ""


class LiveRoomBanRequest(BaseModel):
    participant_id: str
    reason: str = ""
    actor_id: str = ""
    moderator_key: str = ""


class LiveRoomUnbanRequest(BaseModel):
    identity: str
    actor_id: str = ""
    moderator_key: str = ""


class LiveRoomReportRequest(BaseModel):
    reporter_participant_id: str
    reported_participant_id: str
    reason: str
    category: str = "other"


class LiveRoomDismissReportRequest(BaseModel):
    report_id: str
    moderator_key: str = ""


class LiveRoomAskRequest(BaseModel):
    participant_id: str
    question: str
    # Blank -> fall back to the learner's stored language (their profile/device),
    # so the AI answers in the language they speak even if the client omits it.
    language: str = ""


class LiveRoomGiftRequest(BaseModel):
    participant_id: str
    gift_id: str
    recipient_participant_id: str = ""


class LiveRoomReactionRequest(BaseModel):
    participant_id: str
    emoji: str


class GroupGameStartRequest(BaseModel):
    moderator_key: str = ""
    participant_id: str = ""
    game_type: str = "quiz_race"
    prompt: str
    answer: str
    points: int = 25


class GroupGameActionRequest(BaseModel):
    participant_id: str
    answer: str = ""
    cell: int = -1
    letter: str = ""


class MemoryAidRequest(BaseModel):
    content: str
    topic: str = "this lesson"
    preferred_strategy: str = "auto"


class LiveRoomFollowRequest(BaseModel):
    identity: str
    unfollow: bool = False


class CreateLiveRoomRequest(BaseModel):
    title: str
    creator_name: str
    room_size: int = 6
    location: LiveRoomLocation = LiveRoomLocation()


class StartSoloRoomRequest(BaseModel):
    """Open a private 1:1 (AI + one learner) Salareen live room for a lesson."""
    lesson_id: str
    creator_name: str = ""
    student_id: str | None = None
    profile_score: str = ""
    session_length: str = ""
    session_budget_min: int | None = None
    observed_pace: str = ""

    model_config = {"extra": "forbid"}


def _live_room_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="unknown live room")
    if isinstance(exc, RoomFullError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, BannedError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, RateLimitedError):
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, LiveRoomError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


@app.get("/api/live-rooms")
def list_live_rooms(
    lat: float = 0.0,
    lng: float = 0.0,
    radius_km: float = 0.0,
    country: str = "",
    city: str = "",
    grouped: bool = True,
) -> dict:
    """Discover live Salareen rooms — flat list or grouped by country/state/city."""
    from aoep_shared.live_room_discovery import (  # noqa: E402
        group_rooms_by_location,
        room_listing_dict,
    )

    store = _live_rooms()
    rooms = store.list_live(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        country=country,
        city=city,
    )
    cards = [room_listing_dict(r, viewer_lat=lat, viewer_lng=lng) for r in rooms]
    out: dict = {"rooms": cards, "total": len(cards)}
    if grouped:
        out["groups"] = group_rooms_by_location(rooms)
    return out


def _livekit_health(config) -> dict:
    """Inspect the configured LiveKit trio and flag obvious misconfigurations.

    Declared before the ``{room_id}`` route so ``/livekit-status`` is not
    swallowed as a room id.
    """
    url = (config.livekit_url or "").strip()
    key = (config.livekit_api_key or "").strip()
    secret = (config.livekit_api_secret or "").strip()

    def _mask(value: str) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "…"
        return f"{value[:4]}…{value[-4:]}"

    url_is_cloud = ".livekit.cloud" in url
    dev_key = key in ("", "devkey")
    dev_secret = secret in ("", "devsecret")
    likely_misconfigured = url_is_cloud and (dev_key or dev_secret)
    if likely_misconfigured:
        hint = (
            "LiveKit URL points at LiveKit Cloud but the API key/secret are still "
            "dev defaults. Set LIVEKIT_API_KEY / LIVEKIT_API_SECRET to the "
            "project's real credentials (aoep-secrets) and restart the orchestrator."
        )
    elif url_is_cloud:
        hint = (
            "Credentials look configured. If the browser still reports 'WebSocket "
            "is closed before the connection is established', the secret does not "
            "match this project's key — re-copy LIVEKIT_API_SECRET for this exact "
            "key from the LiveKit Cloud dashboard. Add ?probe=1 to verify live."
        )
    else:
        hint = "Using a self-hosted / local LiveKit endpoint."
    return {
        "url": url,
        "url_is_cloud": url_is_cloud,
        "api_key": _mask(key),
        "api_key_configured": not dev_key,
        "api_secret_configured": not dev_secret,
        "using_dev_defaults": dev_key or dev_secret,
        "likely_misconfigured": likely_misconfigured,
        "hint": hint,
    }


@app.get("/api/live-rooms/livekit-status")
def livekit_status(probe: int = 0) -> dict:
    """Report the health of the LiveKit media backend (config + optional live probe).

    The browser can only surface a rejected LiveKit token as the opaque
    'WebSocket is closed before the connection is established'. This endpoint
    turns that into an actionable verdict. ``?probe=1`` performs a server-side
    ``ListRooms`` call to confirm the key/secret actually match the project.
    """
    health = _livekit_health(app.state.config)
    if probe:
        try:
            health["probe"] = app.state.factory.media().verify_credentials()
        except Exception as exc:  # noqa: BLE001
            health["probe"] = {"status": "error", "detail": str(exc)}
    return health


@app.post("/api/live-rooms")
def create_live_room(
    req: CreateLiveRoomRequest,
    authorization: str = Header(default=""),
) -> dict:
    """Instant Salareen room — appears in the discovery feed for other users."""
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402
    from aoep_shared.live_room_discovery import room_listing_dict  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    loc = req.location
    store = _live_rooms()
    try:
        room = store.create_user_room(
            title=req.title.strip() or "Salareen Live",
            creator_name=req.creator_name.strip() or "Host",
            creator_account_id=account_id,
            room_size=req.room_size,
            country=loc.country,
            state=loc.state,
            city=loc.city,
            latitude=loc.latitude,
            longitude=loc.longitude,
        )
    except LiveRoomError as exc:
        raise _live_room_http_error(exc)
    listing = room_listing_dict(room)
    listing["moderator_key"] = room.moderator_key
    return {"room": room.to_dict(), "listing": listing}


@app.post("/api/live-rooms/solo")
def start_solo_live_room(
    req: StartSoloRoomRequest,
    authorization: str = Header(default=""),
) -> dict:
    """Open a solo 1:1 live room — the SAME Salareen classroom UI as a group
    class, but sized for the AI host plus a single learner (room_size=2). A fresh
    teaching session backs it so the AI presents and auto-advances the lesson's
    slides; because the single seat fills on join, the class auto-starts on the
    first tick, just like a full group room."""
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    account_id = account_from_authorization(authorization) or ""
    lesson_id = req.lesson_id.strip()
    if not lesson_id:
        raise HTTPException(status_code=400, detail="lesson_id is required")
    sessions = get_sessions()
    try:
        budget = req.session_budget_min
        if budget is None and (req.profile_score or req.session_length):
            from aoep_shared.catalog_selection import (
                profile_dimensions,
                resolve_session_budget,
            )

            dimensions = profile_dimensions(
                req.profile_score, session_length=req.session_length,
            )
            budget = resolve_session_budget(
                dimensions.get("session_length", req.session_length or "medium"),
                observed_pace=req.observed_pace,
            )
        state = sessions.start_session(
            lesson_id,
            "solo",
            student_id=req.student_id,
            session_budget_min=budget,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {lesson_id}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    slide = sessions.current_slide(state.session_id)
    lesson = sessions.lesson_for(state.session_id)
    room_id = f"solo-{uuid.uuid4().hex[:12]}"
    store = _live_rooms()
    try:
        room = store.open_room(
            room_id=room_id,
            class_id="",
            session_id=state.session_id,
            lesson_id=lesson_id,
            title=f"1:1 · {lesson.title}",
            room_size=2,
            slide_title=slide.title,
            slide_body=slide.body,
            slide_narration=slide.narration,
            creator_name=(req.creator_name or "").strip() or "You",
            creator_account_id=account_id,
        )
    except LiveRoomError as exc:
        raise _live_room_http_error(exc)
    return {"room_id": room.room_id, "room": room.to_dict()}


def _ensure_group_class_room(room_id: str):
    """Lazily open a Salareen live room for a group class.

    Rooms were only created when a class was explicitly "started", so joining a
    scheduled-but-not-started class (or after an orchestrator restart dropped the
    in-memory room) 404'd. This opens/reopens the room on demand from the group
    class record — starting the teaching session if needed — so selecting a
    Salareen room "just works". Returns the room, or None if there is no matching
    Salareen group class (genuine 404).
    """
    store = _live_rooms()
    room = store.get(room_id)
    if room is not None:
        return room
    if not room_id.startswith("class-"):
        return None
    class_id = room_id[len("class-"):]
    # Seed-on-miss (like start_group_class): a fresh replica, a post-restart
    # store, or an evicted entry may not hold this standard class yet. Its
    # deterministic id is reproducible, so materialize it before giving up —
    # otherwise GET/join can't lazily reopen the room and 404s persist.
    gc = _find_group_class(class_id)
    if gc is None or gc.platform != "salareen":
        return None
    if gc.live_room_id:
        existing = store.get(gc.live_room_id)
        if existing is not None:
            return existing

    sessions = get_sessions()
    session_id = gc.session_id
    slide = None
    if session_id:
        try:
            slide = sessions.current_slide(session_id)
        except KeyError:
            session_id = ""  # session was lost (restart) — recreate below
    if not session_id:
        try:
            state = sessions.start_session(gc.lesson_id, "group")
        except KeyError:
            return None
        session_id = state.session_id
        gc.session_id = session_id
        gc.status = "live"
        slide = sessions.current_slide(session_id)

    gc.live_room_id = room_id
    live = store.open_room(  # idempotent: returns the existing room if present
        room_id=room_id,
        class_id=gc.id,
        session_id=session_id,
        lesson_id=gc.lesson_id,
        title=gc.title,
        room_size=gc.room_size,
        slide_title=slide.title,
        slide_body=slide.body,
        slide_narration=slide.narration,
        creator_name=gc.host or "Salareen",
        creator_account_id=gc.instructor_account_id or gc.created_by_account_id,
        **_human_taught_kwargs(gc),
        scheduled_start=gc.start_time,
        duration_seconds=int(gc.duration_min) * 60,
        presence_enabled=True,
        presence_hold_grace_seconds=90,
        presence_stale_seconds=20,
        presence_require_liveness=bool(gc.require_liveness),
        presence_max_faces_allowed=int(gc.max_faces_allowed or 1),
    )
    # Replica reopen / Redis miss: the teaching session may already be mid-lesson
    # (slide index > 0) while the freshly materialized room has presenting=False.
    # Resume presenting silently so "Start class" isn't stuck and clients hear
    # narration — without appending another "Class is starting" chat line.
    if live is not None and not live.presenting and live.status == "live":
        slide_idx = int(getattr(slide, "index", 0) or 0) if slide is not None else 0
        if slide_idx > 0:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            live.presenting = True
            if not live.presentation_started_at:
                live.presentation_started_at = now
                live.slide_started_at = now
            if slide is not None:
                live.slide.index = slide_idx
                live.slide.title = slide.title
                live.slide.body = slide.body
                live.slide.narration = slide.narration
            store._commit(live)  # noqa: SLF001 — resume flag on reopen
    _group_store().save(gc)
    return live


def _ensure_room_or_404(room_id: str):
    """Return the room, LAZILY REOPENING a group-class room that this replica
    doesn't hold. Behind the load balancer a room opened on replica A can be
    absent on replica B, so endpoints that call store.require() directly (tick,
    start-presentation, media-token, call-next, mute, …) 404'd and the class
    couldn't start / mute / advance. Reopening from the (Redis-backed) group
    class record on-miss makes EVERY room action work on any replica. Non-class
    rooms (solo/instant) that are genuinely gone still 404."""
    room = _ensure_group_class_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="unknown live room")
    return room


@app.get("/api/live-rooms/{room_id}")
def get_live_room(
    room_id: str,
    moderator_key: str = "",
    authorization: str = Header(default=""),
) -> dict:
    room = _ensure_group_class_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="unknown live room")
    store = _live_rooms()
    # Lazily close a room that outlived its allotted window even if no client was
    # ticking, so a GET never reports an expired class as still "live".
    if store.should_expire(room_id):
        room = store.end_room(room_id, auto=True)
    if (
        moderator_key
        and moderator_key == room.moderator_key
    ) or _request_is_admin(authorization):
        return room.to_moderator_dict()
    return room.to_dict()


@app.post("/api/live-rooms/{room_id}/join")
def join_live_room(
    room_id: str,
    req: LiveRoomJoinRequest,
    background: BackgroundTasks,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_rewards import account_from_authorization  # noqa: E402

    store = _live_rooms()
    account_id = account_from_authorization(authorization) or ""
    # Open the room on demand for group-class Salareen rooms so joining a
    # scheduled (not-yet-started) class works instead of 404ing.
    ensured_room = _ensure_group_class_room(room_id)
    resolved_room_id = ensured_room.room_id if ensured_room is not None else room_id
    class_id = ""
    if resolved_room_id.startswith("class-"):
        class_id = resolved_room_id[len("class-"):]
        gc = _find_group_class(class_id)
        if gc is not None and gc.attendee_code_required:
            if not req.attendee_code.strip():
                raise HTTPException(status_code=400, detail="attendee_code is required for this class")
            try:
                _group_store().authorize_attendee(
                    class_id,
                    attendee_code=req.attendee_code,
                    account_id=account_id,
                    identity=req.identity,
                )
            except GroupClassError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
    try:
        participant = store.join(
            resolved_room_id,
            req.name,
            identity=req.identity,
            account_id=account_id,
            language=req.language,
            student_id=req.student_id,
            readiness_band=req.readiness_band,
            readiness_score=req.readiness_score,
            primary_style=req.primary_style,
        )
    except (KeyError, LiveRoomError, RoomFullError) as exc:
        raise _live_room_http_error(exc)
    if class_id and account_id:
        gc = _find_group_class(class_id)
        if gc is not None:
            gc.record_host_checkin(account_id)
            _group_store().save(gc)
    if class_id and req.attendee_code.strip():
        try:
            _group_store().authorize_attendee(
                class_id,
                attendee_code=req.attendee_code,
                account_id=account_id,
                identity=participant.identity,
            )
        except GroupClassError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    media = app.state.factory.media()
    token = media.issue_token(
        room=resolved_room_id,
        identity=participant.identity,
        can_publish=participant.can_publish,
    )
    room = store.require(resolved_room_id)
    from aoep_shared.live_room_social import PresenceToast  # noqa: E402
    from aoep_shared.live_room_ws import ws_presence  # noqa: E402

    toast = PresenceToast(kind="join", participant_id=participant.id, name=participant.name)
    _schedule_live_broadcast(
        background,
        resolved_room_id,
        ws_presence(toast.to_dict(), room_id=resolved_room_id, viewer_count=room.viewer_count),
    )
    try:
        _refresh_audience_profile(resolved_room_id)
        room = store.require(resolved_room_id)
        _attach_audience_to_session(resolved_room_id, room.session_id)
    except Exception:
        pass
    return {
        "participant": participant.to_dict(),
        "room": room.to_dict(),
        "media": {
            "room": token.room,
            "identity": token.identity,
            "token": token.token,
            "url": token.url,
        },
        "gift_balance": store.gift_balance_for(participant, authorization),
        "host_follower_count": store.host_follower_count(resolved_room_id),
        "following_host": store.is_following_host(resolved_room_id, participant.identity),
        "is_admin": participant.is_admin,
        # Only give the moderator_key to the scheduled class host (account matches
        # the room's creator_account_id).  A first-joiner who becomes is_admin via
        # the legacy flow (no designated host) must NOT get the key — otherwise any
        # user who joins a Theodore standard class first would appear as the
        # "host teacher" in the live-room UI, overriding the AI presenter.
        "moderator_key": (
            room.moderator_key
            if participant.is_admin
            and room.creator_account_id
            and participant.account_id == room.creator_account_id
            else ""
        ),
    }


def _refresh_audience_profile(room_id: str) -> dict:
    """Rebuild privacy-safe audience aggregates from participant readiness fields."""
    from aoep_shared.audience_profile import (
        LearnerReadinessSnapshot,
        aggregate_audience,
    )

    store = _live_rooms()
    room = store.require(room_id)
    snaps = []
    for p in room.participants.values():
        if p.is_host:
            continue
        if not p.readiness_score and not p.readiness_band:
            continue
        snaps.append(
            LearnerReadinessSnapshot(
                student_id=p.student_id,
                account_id=p.account_id,
                readiness_score=float(p.readiness_score or 0),
                band=p.readiness_band or "developing",
                preferred_language=p.language or "en",
                primary_style=(p.primary_style or "mixed").strip() or "mixed",
            )
        )
    profile = aggregate_audience(snaps).to_prompt_safe()
    store.set_audience_profile(room_id, profile)
    return profile


def _attach_audience_to_session(room_id: str, session_id: str) -> None:
    """Copy room audience aggregates + learner id into the teaching session so
    Theodore's blocking and streaming Q&A paths can adapt."""
    if not session_id:
        return
    store = _live_rooms()
    sessions = get_sessions()
    try:
        room = store.require(room_id)
        session = sessions.store.get(session_id)
        if session is None:
            return
        profile = dict(room.audience_profile or {})
        if not profile.get("learner_count"):
            profile = _refresh_audience_profile(room_id)
        session.audience_profile = profile
        sessions.store.save(session)
        for p in room.participants.values():
            if p.is_host or not p.student_id:
                continue
            counters = sessions.counters_for(session_id)
            if not counters.student_id:
                counters.student_id = p.student_id
            break
    except Exception:
        pass


@app.post("/api/live-rooms/{room_id}/xr/enable")
def live_room_xr_enable(
    room_id: str,
    req: XrLabEnableRequest,
    background: BackgroundTasks,
) -> dict:
    """Enable or disable the XR demonstration lab for a live room (host/admin)."""
    from aoep_shared.xr import default_lab_for_lesson  # noqa: E402
    from aoep_shared.live_room_ws import ws_lab  # noqa: E402

    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)
        if req.moderator_key:
            room.verify_moderator(req.moderator_key)
        elif req.participant_id:
            actor = room.get_participant(req.participant_id)
            if not actor.is_admin and not actor.is_host:
                raise LiveRoomError("only the class admin can enable XR lab")
        else:
            raise LiveRoomError("moderator_key or admin participant_id required")
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)

    lab = default_lab_for_lesson(
        lesson_id=req.lesson_id or room.lesson_id,
        course_id=req.course_id or room.class_id,
        title=req.title or f"Lab: {room.title}",
    )
    store.enable_xr_lab(room_id, lab.to_dict() if req.enabled else {}, enabled=req.enabled)
    room = store.require(room_id)
    _schedule_live_broadcast(
        background,
        room_id,
        ws_lab(lab.to_dict() if req.enabled else {}, room_id=room_id, enabled=req.enabled),
    )
    return {"room": room.to_dict(), "lab": lab.to_dict() if req.enabled else None}


@app.get("/api/live-rooms/{room_id}/xr/lab")
def live_room_xr_lab(room_id: str) -> dict:
    room = _ensure_room_or_404(room_id)
    return {
        "enabled": bool(room.xr_lab_enabled),
        "lab": room.xr_lab,
        "protocol_version": (room.xr_lab or {}).get("protocol_version", "aoep.xr.v1"),
        "attempts": room.xr_attempts,
    }


@app.post("/api/live-rooms/{room_id}/xr/complete")
def live_room_xr_complete(
    room_id: str,
    req: XrCompleteRequest,
    background: BackgroundTasks,
) -> dict:
    """Score a bounded observation batch against the room lab rubric (deterministic)."""
    from aoep_shared.xr import (  # noqa: E402
        XrLabDefinition,
        XrRubricStep,
        observation_from_dict,
        score_attempt,
        default_lab_for_lesson,
    )
    from aoep_shared.live_room_ws import ws_lab_score  # noqa: E402

    if len(req.observations) > 120:
        raise HTTPException(status_code=400, detail="too many observations (max 120)")

    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)
        participant = room.get_participant(req.participant_id)
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)

    raw_lab = room.xr_lab
    if not room.xr_lab_enabled or not raw_lab:
        # Allow complete against default lab when physical assessment is used
        # outside an explicitly enabled room (solo / fallback clients).
        lab_def = default_lab_for_lesson(
            lesson_id=room.lesson_id, course_id=room.class_id, title=room.title
        )
    else:
        steps = [
            XrRubricStep(**s) if isinstance(s, dict) else s
            for s in (raw_lab.get("steps") or [])
        ]
        lab_def = XrLabDefinition(
            lab_id=str(raw_lab.get("lab_id") or req.lab_id or "lab"),
            title=str(raw_lab.get("title") or "XR Lab"),
            course_id=str(raw_lab.get("course_id") or ""),
            lesson_id=str(raw_lab.get("lesson_id") or room.lesson_id),
            protocol_version=str(raw_lab.get("protocol_version") or "aoep.xr.v1"),
            pass_threshold=float(raw_lab.get("pass_threshold") or 0.7),
            provisional=bool(raw_lab.get("provisional", True)),
            steps=steps,
        )

    observations = [observation_from_dict(o.model_dump()) for o in req.observations]
    result = score_attempt(
        lab_def,
        observations,
        student_id=req.student_id or participant.student_id,
        room_id=room_id,
        client_kind=req.client_kind,
    )
    summary = {
        "outcome": result.outcome,
        "score": result.score,
        "provisional": result.provisional,
        "client_kind": result.client_kind,
        "completed_at": result.completed_at,
        "attempt_id": result.attempt_id,
        "lab_id": result.lab_id,
        "evidence_summary": result.evidence_summary,
    }
    store.record_xr_attempt(room_id, req.participant_id, summary)
    # Physical skill hint into participant readiness band (local cache only).
    room = store.require(room_id)
    participant = room.get_participant(req.participant_id)
    if result.outcome == "pass":
        participant.readiness_score = max(float(participant.readiness_score or 0), 80.0)
        participant.readiness_band = "ready"
    elif result.outcome == "needs_work":
        if not participant.readiness_band:
            participant.readiness_band = "needs_support"
    store.set_audience_profile(room_id, dict(room.audience_profile or {}))
    try:
        _refresh_audience_profile(room_id)
    except Exception:
        pass
    _schedule_live_broadcast(
        background,
        room_id,
        ws_lab_score(summary, room_id=room_id, participant_id=req.participant_id),
    )
    return {
        "result": result.to_dict(),
        "room": store.require(room_id).to_dict(),
    }


@app.get("/api/live-rooms/{room_id}/audience-profile")
def live_room_audience_profile(room_id: str, refresh: bool = False) -> dict:
    """Privacy-safe audience readiness aggregates for Theodore / admins."""
    room = _ensure_room_or_404(room_id)
    if refresh or not room.audience_profile:
        profile = _refresh_audience_profile(room_id)
    else:
        profile = dict(room.audience_profile)
    return {"room_id": room_id, "audience_profile": profile}


@app.post("/api/live-rooms/{room_id}/media-token")
def live_room_media_token(room_id: str, req: LiveRoomHandRequest) -> dict:
    """Issue a FRESH LiveKit token for a participant reflecting their CURRENT
    publish right. The hard mutex hinges on this: learners join with can_publish
    False, and when the host/AI grants them the floor the client re-fetches a
    token here (now can_publish True) and reconnects to publish. On losing the
    floor it re-fetches again (can_publish False) so LiveKit refuses to publish."""
    try:
        room = _ensure_room_or_404(room_id)  # reopen if this replica lacks it
        p = room.get_participant(req.participant_id)
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    token = app.state.factory.media().issue_token(
        room=room_id, identity=p.identity, can_publish=p.can_publish,
    )
    return {
        "media": {
            "room": token.room,
            "identity": token.identity,
            "token": token.token,
            "url": token.url,
        },
        "can_publish": p.can_publish,
    }


@app.post("/api/live-rooms/{room_id}/leave")
def leave_live_room(
    room_id: str,
    req: LiveRoomHandRequest,
    background: BackgroundTasks,
) -> dict:
    store = _live_rooms()
    try:
        p = store.require(room_id).get_participant(req.participant_id)
        name = p.name
        pid = p.id
        store.leave(room_id, req.participant_id)
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    room = store.require(room_id)
    from aoep_shared.live_room_social import PresenceToast  # noqa: E402
    from aoep_shared.live_room_ws import ws_presence  # noqa: E402

    toast = PresenceToast(kind="leave", participant_id=pid, name=name)
    _schedule_live_broadcast(
        background,
        room_id,
        ws_presence(toast.to_dict(), room_id=room_id, viewer_count=room.viewer_count),
    )
    return room.to_dict()


_chat_reply_last: _ODict[str, float] = _ODict()  # room:pid -> last reply timestamp
_CHAT_REPLY_LAST_MAX = 5_000
_CHAT_REPLY_COOLDOWN_S = 8.0  # minimum seconds between Theodore replies per participant
import threading as _threading  # noqa: E402
_chat_reply_lock = _threading.Lock()  # guards _chat_reply_last to prevent TOCTOU races
# room_id -> (timestamp, participant_id): track when a floor holder enters
# the confirmation-pending state so the tick watchdog can auto-release if
# the client disconnects before calling finish-turn.
_confirmation_pending: dict[str, tuple[float, str]] = {}


def _chat_theodore_reply(room_id: str, participant_id: str, text: str) -> None:
    # A human-taught class has no Theodore: the instructor answers their own class.
    try:
        if _live_rooms().require(room_id).human_taught:
            return
    except Exception:
        return

    """Reply to a learner chat message from Theodore in a background thread."""
    import time as _time
    key = f"{room_id}:{participant_id}"
    with _chat_reply_lock:
        now = _time.time()
        if now - _chat_reply_last.get(key, 0) < _CHAT_REPLY_COOLDOWN_S:
            return
        _chat_reply_last[key] = now
        if len(_chat_reply_last) > _CHAT_REPLY_LAST_MAX:
            _chat_reply_last.popitem(last=False)  # evict oldest entry

    store = _live_rooms()
    try:
        room = store.require(room_id)
        if room.status == "ended" or not room.session_id:
            return
        sessions = get_sessions()
        learner = room.get_participant(participant_id)
        name = learner.name if learner else "the learner"
        lang = (learner.language if learner else None) or "en"
        # Ask Theodore to reply conversationally to the chat message.
        prompt = (
            f"{name} said in the class chat: \"{text}\"\n\n"
            "Respond briefly and warmly in one or two sentences. "
            "Stay on the topic of the lesson if relevant, otherwise be friendly and encouraging."
        )
        try:
            chunks = []
            for chunk in sessions.ask_stream(room.session_id, prompt, language=lang):
                if chunk:
                    chunks.append(chunk)
            reply_text = "".join(str(c) if isinstance(c, dict) else c for c in chunks).strip()
            if not reply_text:
                reply_text = (sessions.ask(room.session_id, prompt, language=lang).text or "").strip()
        except Exception:  # noqa: BLE001
            return
        if not reply_text:
            return
        host_msg = store.post_host_message(room_id, reply_text)
        from aoep_shared.live_room_ws import ws_chat  # noqa: E402
        _broadcast_threadsafe(room_id, ws_chat(asdict(host_msg), room_id=room_id))
        # Also broadcast as a host_delta so the TTS effect fires for all participants.
        _broadcast_threadsafe(
            room_id,
            ws_host_delta(text=reply_text, done=True, asker=name, room_id=room_id),
        )
    except Exception:  # noqa: BLE001
        pass


@app.post("/api/live-rooms/{room_id}/chat")
def live_room_chat(
    room_id: str,
    req: LiveRoomChatRequest,
    background: BackgroundTasks,
) -> dict:
    store = _live_rooms()
    try:
        _ensure_room_or_404(room_id)
        msg = store.post_chat(room_id, req.participant_id, req.text)
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    from aoep_shared.live_room_ws import ws_chat  # noqa: E402

    _schedule_live_broadcast(
        background,
        room_id,
        ws_chat(asdict(msg), room_id=room_id),
    )
    # Trigger Theodore to reply to the learner's chat message in the background.
    if req.text.strip():
        background.add_task(
            _chat_theodore_reply, room_id, req.participant_id, req.text.strip()
        )
    return {"message": asdict(msg), "room": store.require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/raise-hand")
def live_room_raise_hand(room_id: str, req: LiveRoomHandRequest) -> dict:
    try:
        _ensure_room_or_404(room_id)
        p = _live_rooms().toggle_hand(room_id, req.participant_id, question=req.question)
    except (KeyError, LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    room = _live_rooms().require(room_id)
    return {
        "participant": p.to_dict(),
        "queue_position": room.queue_position(req.participant_id),
        "room": room.to_dict(),
    }


@app.post("/api/live-rooms/{room_id}/queue/join")
def live_room_queue_join(room_id: str, req: LiveRoomQueueRequest) -> dict:
    try:
        _ensure_room_or_404(room_id)
        entry = _live_rooms().join_queue(room_id, req.participant_id, question=req.question)
    except (KeyError, LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    room = _live_rooms().require(room_id)
    return {"entry": entry.to_dict(), "room": room.to_dict()}


@app.post("/api/live-rooms/{room_id}/queue/leave")
def live_room_queue_leave(room_id: str, req: LiveRoomHandRequest) -> dict:
    try:
        _ensure_room_or_404(room_id)
        _live_rooms().leave_queue(room_id, req.participant_id)
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    return {"room": _live_rooms().require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/queue/call-next")
def live_room_call_next(
    room_id: str,
    req: LiveRoomTurnRequest,
    background: BackgroundTasks,
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        mod = _mod_key_for(_ensure_room_or_404(room_id), req.moderator_key, authorization)
        speaker = store.call_next(room_id, moderator_key=mod)
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    room = store.require(room_id).to_dict()
    from aoep_shared.live_room_ws import ws_queue  # noqa: E402

    _schedule_live_broadcast(background, room_id, ws_queue(room, room_id=room_id))
    return {
        "speaker": speaker.to_dict() if speaker else None,
        "room": room,
    }


@app.post("/api/live-rooms/{room_id}/queue/call-on")
def live_room_call_on(
    room_id: str,
    req: LiveRoomTurnRequest,
    background: BackgroundTasks,
    authorization: str = Header(default=""),
) -> dict:
    """Host/AI gives the floor to a SPECIFIC learner (picks who holds the mic),
    preempting the current speaker. Preserves the single-speaker mutex."""
    store = _live_rooms()
    try:
        mod = _mod_key_for(_ensure_room_or_404(room_id), req.moderator_key, authorization)
        speaker = store.call_on(room_id, req.participant_id, moderator_key=mod)
    except (KeyError, LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    room = store.require(room_id).to_dict()
    from aoep_shared.live_room_ws import ws_queue  # noqa: E402

    _schedule_live_broadcast(background, room_id, ws_queue(room, room_id=room_id))
    return {"speaker": speaker.to_dict() if speaker else None, "room": room}


@app.post("/api/live-rooms/{room_id}/queue/finish-turn")
def live_room_finish_turn(
    room_id: str,
    req: LiveRoomTurnRequest,
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)
        pid = req.participant_id or room.floor_participant_id
        if not pid:
            raise LiveRoomError("no one has the floor")
        mod = _mod_key_for(room, req.moderator_key, authorization)
        store.finish_turn(room_id, pid, moderator_key=mod)
        _confirmation_pending.pop(room_id, None)  # clear watchdog on normal finish
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    return {"room": store.require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/mute")
def live_room_mute(
    room_id: str,
    req: LiveRoomMuteRequest,
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)
        mod = _mod_key_for(room, req.moderator_key, authorization)
        # The platform admin muting a learner acts as host (by_host) even without
        # the room's key; a learner without rights can still only mute themselves.
        by_host = req.by_host or (mod == room.moderator_key and mod != "" and req.participant_id != req.actor_id)
        # A self-mute (no explicit actor) has the participant as its own actor; a
        # host/moderator mute defaults the actor to the AI host. Defaulting to the
        # host for BOTH made self-mute fail with "learners can only mute themselves".
        actor_id = req.actor_id or (AI_HOST_ID if by_host else req.participant_id)
        p = store.set_mute(
            room_id,
            req.participant_id,
            muted=req.muted,
            by_host=by_host,
            actor_id=actor_id,
            moderator_key=mod,
        )
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    return {"participant": p.to_dict(), "room": _live_rooms().require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/ban")
def live_room_ban(
    room_id: str,
    req: LiveRoomBanRequest,
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        mod = _mod_key_for(_ensure_room_or_404(room_id), req.moderator_key, authorization)
        banned = store.ban_participant(
            room_id,
            req.participant_id,
            actor_id=req.actor_id or AI_HOST_ID,
            reason=req.reason,
            moderator_key=mod,
        )
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    return {"banned": banned.to_dict(), "room": _live_rooms().require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/unban")
def live_room_unban(
    room_id: str,
    req: LiveRoomUnbanRequest,
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        mod = _mod_key_for(_ensure_room_or_404(room_id), req.moderator_key, authorization)
        store.unban(
            room_id,
            req.identity,
            actor_id=req.actor_id or AI_HOST_ID,
            moderator_key=mod,
        )
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    return {"room": _live_rooms().require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/report")
def live_room_report(room_id: str, req: LiveRoomReportRequest) -> dict:
    """Learner reports another participant for moderator review."""
    try:
        report = _live_rooms().report_participant(
            room_id,
            req.reporter_participant_id,
            req.reported_participant_id,
            reason=req.reason,
            category=req.category,
        )
    except (KeyError, LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    return {
        "report": report.to_dict(),
        "room": _live_rooms().require(room_id).to_dict(),
    }


@app.post("/api/live-rooms/{room_id}/reports/dismiss")
def live_room_dismiss_report(
    room_id: str,
    req: LiveRoomDismissReportRequest,
    authorization: str = Header(default=""),
) -> dict:
    """Moderator dismisses a user report without banning."""
    store = _live_rooms()
    try:
        mod = _mod_key_for(_ensure_room_or_404(room_id), req.moderator_key, authorization)
        report = store.dismiss_report(
            room_id,
            req.report_id,
            moderator_key=mod,
        )
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    return {
        "report": report.to_dict(),
        "room": _live_rooms().require(room_id).to_moderator_dict(),
    }


def _request_is_admin(authorization: str) -> bool:
    """True when the Bearer token is a platform admin (admin@salareen.com), who
    may moderate ANY live room without holding that room's moderator key."""
    if not authorization:
        return False
    from aoep_shared.live_room_rewards import is_admin_from_authorization  # noqa: E402

    return is_admin_from_authorization(authorization)


def _mod_key_for(room, provided_key: str, authorization: str) -> str:
    """The moderator key to use for a request: the caller's own valid key, or the
    room's real key when the request comes from the platform admin — so the admin
    can start/mute/moderate/close any room without holding its key."""
    if provided_key and provided_key == room.moderator_key:
        return provided_key
    if _request_is_admin(authorization):
        return room.moderator_key
    return provided_key


def _authorize_room_admin(room, req: "LiveRoomTurnRequest", authorization: str = "") -> None:
    """Allow the class admin (first joiner), a moderator_key holder, OR the
    platform admin (admin@salareen.com, by Bearer token)."""
    if req.moderator_key and req.moderator_key == room.moderator_key:
        return
    if _request_is_admin(authorization):
        return
    if req.participant_id:
        p = room.get_participant(req.participant_id)
        if p.is_admin:
            return
    raise LiveRoomError("only the class admin can do that")


def _advance_room_slide(room_id: str, background: BackgroundTasks) -> dict:
    """Advance the lesson one slide (shared by the admin endpoint + auto-advance).
    Resets the per-slide timer and picks up any waiting Q&A hand."""
    store = _live_rooms()
    room = store.require(room_id)
    sessions = get_sessions()
    sid = room.session_id
    try:
        slide = sessions.advance(sid)
        lesson = sessions.lesson_for(sid)
        session = sessions.get_session(sid)
    except KeyError:
        # The teaching session was lost (e.g. the orchestrator restarted while the
        # room persisted in Redis). Re-create a session bound to the room's lesson,
        # resume at the current slide, and advance — so the class keeps moving
        # instead of getting stuck on slide 1.
        if sessions.curriculum.get(room.lesson_id) is None:
            raise HTTPException(status_code=404, detail="teaching session not found")
        recovered = sessions.start_session(room.lesson_id, "group")
        sid = recovered.session_id
        for _ in range(max(0, room.slide.index if room.slide else 0)):
            sessions.advance(sid)
        store.rebind_session(room_id, sid)
        slide = sessions.advance(sid)
        lesson = sessions.lesson_for(sid)
        session = sessions.get_session(sid)
    narration = " ".join((slide.narration or slide.body or slide.title).split())[:500]
    store.update_slide(
        room_id,
        index=session.current_slide,
        title=slide.title,
        body=slide.body,
        narration=slide.narration,
    )
    store.note_slide_started(room_id)  # reset the auto-advance dwell timer
    if narration:
        store.post_host_message(room_id, f"📖 {slide.title} — {narration}")
    auto_speaker = store.auto_call_next_if_waiting(room_id)
    slide_dict = store.require(room_id).slide.to_dict()
    room_dict = store.require(room_id).to_dict()
    from aoep_shared.live_room_ws import ws_slide  # noqa: E402

    _schedule_live_broadcast(background, room_id, ws_slide(slide_dict, room_id=room_id))
    return {
        "slide": slide_dict,
        "room": room_dict,
        "lesson_title": lesson.title,
        "auto_called_on": auto_speaker.to_dict() if auto_speaker else None,
    }


def _address_queue(room_id: str, background: BackgroundTasks) -> "dict | None":
    # Only Theodore auto-answers the Q&A queue; a human instructor does it live.
    try:
        if _live_rooms().require(room_id).human_taught:
            return None
    except Exception:
        return None

    """AI host pauses the class to address the Q&A queue: answer the next typed
    question itself (no human moderator needed), else call the next raised hand
    to the floor. Returns a summary, or None when there's nothing to address.

    This is what makes "join Q&A queue" get handled — the class already pauses
    auto-advance while the queue is non-empty; here Theodore actually replies.
    Also serves as the server-side watchdog: if a floor holder is stuck in the
    confirmation-pending state for >30 s (client disconnected), auto-releases.
    """
    store = _live_rooms()
    try:
        room = store.require(room_id)
    except KeyError:
        return None
    if room.status != "live" or not room.presenting:
        return None

    # Server-side safety net: release the floor if the client disconnected while
    # waiting for confirmation. Timestamps live in _confirmation_pending (below).
    import time as _time
    pending = _confirmation_pending.get(room_id)
    if pending:
        pending_at, pending_pid = pending
        if (_time.time() - pending_at) > 30:
            _confirmation_pending.pop(room_id, None)
            try:
                store.finish_turn(room_id, pending_pid)
                from aoep_shared.live_room_ws import ws_room_snapshot  # noqa: E402
                _broadcast_threadsafe(
                    room_id,
                    ws_room_snapshot(store.require(room_id).to_dict(), room_id=room_id),
                )
            except Exception:  # noqa: BLE001
                pass
    from aoep_shared.live_room_ws import ws_room_snapshot  # noqa: E402

    entry = store.next_unanswered_question(room_id)
    if entry is not None:
        sessions = get_sessions()
        try:
            learner = room.get_participant(entry.participant_id)
            name, lang = learner.name, (learner.language or "en")
        except LiveRoomError:
            name, lang = "there", "en"
        try:
            _attach_audience_to_session(room_id, room.session_id)
            answer = sessions.ask(room.session_id, entry.question, language=lang)
        except Exception:  # noqa: BLE001 - never let Q&A crash the tick
            return None
        # Theodore acknowledges the pause, answers, and clears the question.
        store.post_host_message(room_id, f"🙋 Let's pause for a question from {name}: \u201c{entry.question}\u201d")
        store.post_host_message(room_id, f"@{name} {answer.text}")
        store.resolve_question(room_id, entry.id)
        room_dict = store.require(room_id).to_dict()
        _schedule_live_broadcast(background, room_id, ws_room_snapshot(room_dict, room_id=room_id))
        return {"answered_participant": entry.participant_id, "entry_id": entry.id}

    # No typed questions left — give the next raised hand the floor so people who
    # just want to speak are acknowledged too.
    speaker = store.auto_call_next_if_waiting(room_id)
    if speaker is not None:
        room_dict = store.require(room_id).to_dict()
        _schedule_live_broadcast(background, room_id, ws_room_snapshot(room_dict, room_id=room_id))
        return {"called_on": speaker.id}
    return None


@app.post("/api/live-rooms/{room_id}/advance")
def live_room_advance(
    room_id: str,
    background: BackgroundTasks,
    req: LiveRoomTurnRequest = LiveRoomTurnRequest(),
    authorization: str = Header(default=""),
) -> dict:
    """Advance the slide — class admin, moderator, or platform admin only (the AI
    auto-advances otherwise)."""
    try:
        _authorize_room_admin(_ensure_room_or_404(room_id), req, authorization)
    except (LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    return _advance_room_slide(room_id, background)


@app.post("/api/live-rooms/{room_id}/start-presentation")
def live_room_start_presentation(
    room_id: str,
    background: BackgroundTasks,
    req: LiveRoomTurnRequest = LiveRoomTurnRequest(),
    authorization: str = Header(default=""),
) -> dict:
    """Start the class presentation — class admin (first joiner), moderator key,
    or the platform admin (admin@salareen.com) on ANY room."""
    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)  # reopen if this replica lacks it
        gc = _group_class_for_room(room_id)
        if gc is not None:
            _require_host_can_teach(gc)
        mod = _mod_key_for(room, req.moderator_key, authorization)
        room = store.start_presentation(
            room_id, participant_id=req.participant_id, moderator_key=mod,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    except (LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    room_dict = room.to_dict()
    from aoep_shared.live_room_ws import ws_room_snapshot  # noqa: E402

    _schedule_live_broadcast(background, room_id, ws_room_snapshot(room_dict, room_id=room_id))
    return {"room": room_dict, "presenting": room.presenting}


@app.post("/api/live-rooms/{room_id}/presence-report")
def live_room_presence_report(
    room_id: str,
    req: LiveRoomPresenceReportRequest,
) -> dict:
    store = _live_rooms()
    _ensure_room_or_404(room_id)
    observed_at = None
    if req.observed_at.strip():
        from datetime import datetime

        try:
            observed_at = datetime.fromisoformat(req.observed_at.strip().replace("Z", "+00:00"))
        except ValueError:
            observed_at = None
    try:
        presence = store.report_presence(
            room_id,
            participant_id=req.participant_id,
            present=req.present,
            face_count=req.face_count,
            liveness_state=req.liveness_state,
            liveness_score=req.liveness_score,
            reason=req.reason,
            source=req.source,
            observed_at=observed_at,
        )
        room = store.require(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    except (LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    return {"room": room.to_dict(), "presence": presence}


@app.post("/api/live-rooms/{room_id}/tick")
def live_room_tick(
    room_id: str,
    background: BackgroundTasks,
    pid: str = "",
    moderator_key: str = "",
    authorization: str = Header(default=""),
) -> dict:
    """Heartbeat the room clock AND presence. ``pid`` is the caller's participant
    id: it refreshes their presence heartbeat and prunes learners who went stale
    (closed the browser/app without leaving). Also auto-starts the class (full or
    5 min past the scheduled time), auto-advances slides, and auto-ends/expires
    when the allotted time is up. Any client may call this periodically; all
    actions are idempotent/rate-guarded server-side."""
    store = _live_rooms()
    room = _ensure_room_or_404(room_id)  # reopen on this replica if the LB routed us elsewhere
    # Presence: mark the caller alive, then drop anyone whose heartbeat went stale.
    if pid:
        store.touch(room_id, pid)
    prune_ttl = 45
    if getattr(room, "presence_policy", None) and room.presence_policy.enabled:
        prune_ttl = max(prune_ttl, int(room.presence_policy.grace_seconds) + 15)
    pruned = store.prune_stale(room_id, ttl_seconds=prune_ttl)
    presence_changed = store.evaluate_presence_holds(room_id)
    started = advanced = None
    ended = False
    addressed = None
    if store.should_auto_start(room_id):
        gc = _group_class_for_room(room_id)
        try:
            if gc is not None:
                _require_host_can_teach(gc)
            store.start_presentation(room_id, auto=True)
            started = True
        except LiveRoomError:
            started = False
    # Auto-end takes priority over advancing: when the allotted class time is up
    # (presenting past its duration, or a scheduled room whose window fully
    # lapsed), close the room so clients show the "class complete" excuse.
    if store.should_auto_end(room_id) or store.should_expire(room_id):
        ended_room = store.end_room(room_id, auto=True)
        ended = True
        # Keep the group-class record in sync so the scheduled class stops showing
        # as LIVE/joinable in the listing once its room has ended.
        gc = _group_store().get(ended_room.class_id) if ended_room.class_id else None
        if gc is not None:
            gc.settle_host_payout()
            _group_store().set_status(gc.id, "ended")
            _group_store().save(gc)
    else:
        # Address the Q&A queue FIRST (Theodore pauses to answer a queued
        # question / call on a raised hand); only auto-advance when the queue is
        # clear (should_auto_advance is already false while the queue is busy).
        addressed = _address_queue(room_id, background)
        if not addressed and store.should_auto_advance(room_id):
            try:
                advanced = _advance_room_slide(room_id, background)
            except HTTPException:
                advanced = None  # never let a transient advance failure break the tick
    room = store.require(room_id)
    is_moderator = (
        bool(moderator_key) and moderator_key == room.moderator_key
    ) or _request_is_admin(authorization)
    room_dict = room.to_moderator_dict() if is_moderator else room.to_dict()
    from aoep_shared.live_room_ws import ws_room_snapshot  # noqa: E402

    if (started or ended or pruned or presence_changed) and not advanced and not addressed:
        # Never broadcast moderator-only profile fields to ordinary learners.
        public_room = room.to_dict()
        _schedule_live_broadcast(
            background,
            room_id,
            ws_room_snapshot(public_room, room_id=room_id),
        )
    return {
        "room": room_dict,
        "auto_started": bool(started),
        "auto_advanced": advanced["slide"] if advanced else None,
        "auto_ended": ended,
        "addressed_queue": addressed,
        "pruned": pruned,
    }


@app.post("/api/live-rooms/{room_id}/ask")
def live_room_ask(room_id: str, req: LiveRoomAskRequest) -> dict:
    """Learner asks a question; Theodore answers in the room chat."""
    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)
        learner = room.get_participant(req.participant_id)
    except LiveRoomError as exc:
        raise _live_room_http_error(exc)
    sessions = get_sessions()
    try:
        mode, entry = store.ask_when_ready(room_id, req.participant_id, req.question)
        if mode == "queued":
            return {
                "queued": True,
                "queue_position": entry.position if entry else 0,
                "entry": entry.to_dict() if entry else None,
                "room": store.require(room_id).to_dict(),
            }
        store.post_chat(room_id, req.participant_id, req.question)
        # Answer in the asker's language: explicit request wins, else the language
        # they joined with (profile/device), else English.
        lang = (req.language or "").strip() or learner.language or "en"
        _attach_audience_to_session(room_id, room.session_id)
        answer = sessions.ask(room.session_id, req.question, language=lang)
        host_msg = store.post_host_message(
            room_id,
            f"@{learner.name} {answer.text}",
        )
        store.finish_turn(room_id, req.participant_id)
        _confirmation_pending.pop(room_id, None)
    except KeyError:
        raise HTTPException(status_code=404, detail="teaching session not found")
    except LiveRoomError as exc:
        raise _live_room_http_error(exc)
    return {
        "queued": False,
        "answer": answer.model_dump(),
        "host_message": asdict(host_msg),
        "room": store.require(room_id).to_dict(),
    }


def _split_finished_sentences(buf: str) -> "tuple[list[str], str]":
    """Split a streaming buffer into complete sentences + the trailing remainder.

    Used to broadcast the AI host's answer to the room in speakable chunks (so
    every participant's TTS can start on the first sentence) instead of one WS
    frame per token."""
    import re as _re

    parts = _re.split(r"(?<=[.!?…])\s+", buf)
    if len(parts) <= 1:
        return [], buf
    return [p for p in parts[:-1] if p.strip()], parts[-1]


def _iter_host_answer(room_id: str, participant_id: str, question: str, language: str = ""):
    """Stream Theodore's answer for a live-room question.

    Yields SSE-friendly event dicts (``queued`` | ``delta`` | ``done``) for the
    asker's HTTP stream AND broadcasts ``host_delta`` frames over the room's
    WebSocket so every participant sees/hears the answer build in real time. The
    LLM (Nemotron when configured) is consumed via the streaming ``ask_stream``
    path; it falls back to the blocking grounded answer if streaming yields
    nothing. Side effects mirror the blocking ``/ask``: post the learner's
    question, post the final host message, and clear the turn.
    """
    store = _live_rooms()
    room = store.require(room_id)
    sessions = get_sessions()
    learner = room.get_participant(participant_id)
    name = learner.name
    lang = (language or "").strip() or learner.language or "en"

    mode, entry = store.ask_when_ready(room_id, participant_id, question)
    if mode == "queued":
        yield {
            "type": "queued",
            "queue_position": entry.position if entry else 0,
            "entry": entry.to_dict() if entry else None,
            "room": store.require(room_id).to_dict(),
        }
        return

    store.post_chat(room_id, participant_id, question)
    _attach_audience_to_session(room_id, room.session_id)
    _broadcast_threadsafe(room_id, ws_host_delta(asker=name, text="", room_id=room_id))
    # Bug fix: stamp the watchdog BEFORE streaming so a mid-stream client
    # disconnect (which abandons the generator) still records the pending state
    # and the tick watchdog can auto-release the floor after 30 s.
    import time as _time
    _confirmation_pending[room_id] = (_time.time(), participant_id)

    streamed: list[str] = []
    buf = ""
    try:
        for chunk in sessions.ask_stream(room.session_id, question, language=lang):
            if not chunk:
                continue
            chunk_text = chunk.get("text", "") if isinstance(chunk, dict) else chunk
            streamed.append(chunk_text)
            yield {"type": "delta", "text": chunk_text}
            buf += chunk_text
            segments, buf = _split_finished_sentences(buf)
            for seg in segments:
                _broadcast_threadsafe(
                    room_id, ws_host_delta(text=seg + " ", asker=name, room_id=room_id)
                )
    except Exception:  # noqa: BLE001 - never let a model hiccup crash the room
        streamed = []

    text = "".join(streamed).strip()
    if not text:
        # Streaming produced nothing (no model server / error) -> grounded blocking
        # answer so the class still gets a real reply.
        try:
            text = sessions.ask(room.session_id, question, language=lang).text
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            yield {"type": "delta", "text": text}
            _broadcast_threadsafe(room_id, ws_host_delta(text=text, asker=name, room_id=room_id))
    elif buf.strip():
        _broadcast_threadsafe(room_id, ws_host_delta(text=buf.strip(), asker=name, room_id=room_id))

    # Bug fix: if the LLM produced no text at all, clear the watchdog stamp.
    # The client's hostAnswer effect returns early when text is empty, so no
    # confirmation UI starts and the floor would be held forever without this.
    if not text:
        _confirmation_pending.pop(room_id, None)

    # Append a confirmation prompt so the learner always gets a chance to
    # follow up before the floor is released.
    confirmation_prompt = "Does that answer your question?"
    if text:
        _broadcast_threadsafe(
            room_id,
            ws_host_delta(text=" " + confirmation_prompt, asker=name, room_id=room_id),
        )
    full_text = (text + " " + confirmation_prompt).strip() if text else ""

    host_msg = store.post_host_message(room_id, f"@{name} {full_text}") if full_text else None
    # The floor is held open for the learner's confirmation. The watchdog stamp
    # was already set before streaming started (see above) so it is always
    # recorded even if the client disconnected mid-stream.
    room_dict = store.require(room_id).to_dict()
    yield {"type": "awaiting_confirmation", "asker": name, "confirmation": confirmation_prompt}
    _broadcast_threadsafe(
        room_id,
        ws_host_delta(
            done=True,
            message=asdict(host_msg) if host_msg else None,
            asker=name,
            room_id=room_id,
            awaiting_confirmation=True,
        ),
    )
    _broadcast_threadsafe(room_id, ws_room_snapshot(room_dict, room_id=room_id))
    yield {
        "type": "done",
        "text": text,
        "host_message": asdict(host_msg) if host_msg else None,
        "room": room_dict,
    }


@app.post("/api/live-rooms/{room_id}/ask-stream")
def live_room_ask_stream(room_id: str, req: LiveRoomAskRequest):
    """Streaming variant of ``/ask``: Server-Sent Events of Theodore's answer as
    it is generated (real-time, low-latency voice), while also broadcasting
    ``host_delta`` frames to the whole room over WebSocket. Each SSE frame is
    ``data: {json}\\n\\n``; events are ``queued`` | ``delta`` | ``done``. Powered
    by the Nemotron agent when configured. The blocking ``/ask`` remains for
    clients that cannot read a stream."""
    import json as _json

    from fastapi.responses import StreamingResponse

    store = _live_rooms()
    try:
        _ensure_room_or_404(room_id)
        store.require(room_id).get_participant(req.participant_id)
    except LiveRoomError as exc:
        raise _live_room_http_error(exc)

    def _events():
        try:
            for event in _iter_host_answer(
                room_id, req.participant_id, req.question, req.language
            ):
                yield f"data: {_json.dumps(event)}\n\n"
        except KeyError:
            yield f"data: {_json.dumps({'type': 'error', 'detail': 'teaching session not found'})}\n\n"
        except LiveRoomError as exc:
            yield f"data: {_json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        _events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/live-rooms/{room_id}/record/start")
def live_room_record_start(room_id: str) -> dict:
    try:
        rec = _live_rooms().start_recording(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    return {"recording": rec.to_dict(), "room": _live_rooms().require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/record/stop")
def live_room_record_stop(room_id: str) -> dict:
    try:
        rec = _live_rooms().stop_recording(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    return {"recording": rec.to_dict(), "room": _live_rooms().require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/end")
def live_room_end(
    room_id: str,
    req: LiveRoomTurnRequest = LiveRoomTurnRequest(),
    authorization: str = Header(default=""),
) -> dict:
    """Close a live session (status=ended). Allowed for the room's moderator-key
    holder or the platform admin (admin@salareen.com) on ANY room."""
    store = _live_rooms()
    try:
        room = store.require(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    if _mod_key_for(room, req.moderator_key, authorization) != room.moderator_key:
        raise HTTPException(status_code=403, detail="only a moderator or the platform admin can close this session")
    room = store.end_room(room_id)
    gc = _group_store().get(room.class_id)
    if gc is not None:
        _group_store().set_status(gc.id, "ended")
    return room.to_dict()


@app.delete("/api/live-rooms/{room_id}")
def delete_live_room(room_id: str, authorization: str = Header(default="")) -> dict:
    """Delete a live session entirely (admin cleanup). Platform admin only
    (admin@salareen.com). Ends it first so any connected clients are excused,
    then removes it from the store."""
    store = _live_rooms()
    if not _request_is_admin(authorization):
        raise HTTPException(status_code=403, detail="platform admin only")
    room = store.get(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="unknown live room")
    try:
        store.end_room(room_id)  # flip to ended so any clients show the farewell/exit
    except (KeyError, LiveRoomError):
        pass
    gc = _group_store().get(room.class_id)
    if gc is not None:
        _group_store().set_status(gc.id, "ended")
    store.delete(room_id)
    return {"deleted": True, "room_id": room_id}


@app.get("/api/live-rooms/gifts/catalog")
def live_room_gift_catalog() -> dict:
    return {"gifts": _live_rooms().gift_catalog()}


@app.get("/api/live-rooms/games/catalog")
def live_room_game_catalog() -> dict:
    from aoep_shared.live_room_games import GAME_LIBRARY

    return {"games": list(GAME_LIBRARY)}


@app.get("/api/teaching/memory-aids/catalog")
def memory_aid_catalog() -> dict:
    from aoep_shared.memory_teaching import MEMORY_STRATEGIES

    return {"strategies": list(MEMORY_STRATEGIES)}


@app.post("/api/teaching/memory-aids/generate")
def generate_memory_aid(req: MemoryAidRequest) -> dict:
    from aoep_shared.memory_teaching import build_memory_aid

    try:
        return build_memory_aid(
            req.content,
            topic=req.topic,
            preferred=req.preferred_strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/live-rooms/{room_id}/games/start")
def live_room_game_start(
    room_id: str,
    req: GroupGameStartRequest,
    background: BackgroundTasks,
    authorization: str = Header(default=""),
) -> dict:
    from aoep_shared.live_room_games import public_game
    from aoep_shared.live_room_ws import ws_game

    store = _live_rooms()
    try:
        room = _ensure_room_or_404(room_id)
        if _request_is_admin(authorization):
            pass
        elif req.moderator_key:
            room.verify_moderator(req.moderator_key)
        elif req.participant_id:
            actor = room.get_participant(req.participant_id)
            if not actor.is_admin and not actor.is_host:
                raise LiveRoomError("only the class host/admin can start games")
        else:
            raise LiveRoomError("moderator authorization required")
        room = store.start_group_game(
            room_id,
            game_type=req.game_type,
            prompt=req.prompt,
            answer=req.answer,
            points=req.points,
        )
    except (KeyError, LiveRoomError, ValueError) as exc:
        raise _live_room_http_error(exc)
    game = public_game(room.group_game) or {}
    _schedule_live_broadcast(
        background, room_id, ws_game(game, room_id=room_id, room=room.to_dict())
    )
    return {"game": game, "room": room.to_dict()}


@app.post("/api/live-rooms/{room_id}/games/action")
def live_room_game_action(
    room_id: str,
    req: GroupGameActionRequest,
    background: BackgroundTasks,
) -> dict:
    from aoep_shared.live_room_games import public_game
    from aoep_shared.live_room_rewards import earn_rewards_internal
    from aoep_shared.live_room_ws import ws_game

    store = _live_rooms()
    try:
        room, event = store.play_group_game(
            room_id,
            req.participant_id,
            answer=req.answer,
            cell=req.cell,
            letter=req.letter,
        )
        participant = room.get_participant(req.participant_id)
    except (KeyError, LiveRoomError, ValueError) as exc:
        raise _live_room_http_error(exc)
    if event.get("points") and participant.account_id:
        earn_rewards_internal(
            participant.account_id,
            int(event["points"]),
            reason=f"group_game:{(room.group_game or {}).get('type', 'game')}",
            ref=room_id,
        )
    game = public_game(room.group_game) or {}
    _schedule_live_broadcast(
        background, room_id,
        ws_game(game, room_id=room_id, event=event, room=room.to_dict())
    )
    return {"game": game, "event": event, "room": room.to_dict()}


@app.get("/api/live-rooms/{room_id}/gift-balance")
def live_room_gift_balance(
    room_id: str,
    identity: str = "",
    participant_id: str = "",
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        room = store.require(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    if participant_id:
        try:
            participant = room.get_participant(participant_id)
            return {"balance": store.gift_balance_for(participant, authorization)}
        except LiveRoomError:
            pass
    return {"balance": store.gift_balance(identity)}


@app.post("/api/live-rooms/{room_id}/gifts/send")
def live_room_send_gift(
    room_id: str,
    req: LiveRoomGiftRequest,
    background: BackgroundTasks,
    authorization: str = Header(default=""),
) -> dict:
    store = _live_rooms()
    try:
        gift, balance = store.send_gift(
            room_id,
            req.participant_id,
            gift_id=req.gift_id,
            recipient_participant_id=req.recipient_participant_id,
            authorization=authorization,
        )
    except (KeyError, LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    from aoep_shared.live_room_ws import ws_gift  # noqa: E402

    _schedule_live_broadcast(
        background,
        room_id,
        ws_gift(gift.to_dict(), room_id=room_id, sender_balance=balance),
    )
    return {
        "gift": gift.to_dict(),
        "sender_balance": balance,
        "room": store.require(room_id).to_dict(),
    }


@app.post("/api/live-rooms/{room_id}/reactions")
def live_room_reaction(
    room_id: str,
    req: LiveRoomReactionRequest,
    background: BackgroundTasks,
) -> dict:
    store = _live_rooms()
    try:
        _ensure_room_or_404(room_id)
        reaction = store.send_reaction(room_id, req.participant_id, emoji=req.emoji)
    except (KeyError, LiveRoomError, BannedError) as exc:
        raise _live_room_http_error(exc)
    from aoep_shared.live_room_ws import ws_reaction  # noqa: E402

    _schedule_live_broadcast(
        background,
        room_id,
        ws_reaction(reaction.to_dict(), room_id=room_id),
    )
    return {"reaction": reaction.to_dict(), "room": store.require(room_id).to_dict()}


@app.post("/api/live-rooms/{room_id}/follow")
def live_room_follow_host(
    room_id: str,
    req: LiveRoomFollowRequest,
    background: BackgroundTasks,
) -> dict:
    store = _live_rooms()
    try:
        following, count = store.follow_host(
            room_id, req.identity, unfollow=req.unfollow
        )
    except (KeyError, LiveRoomError) as exc:
        raise _live_room_http_error(exc)
    from aoep_shared.live_room_ws import ws_follow  # noqa: E402

    _schedule_live_broadcast(
        background,
        room_id,
        ws_follow(following, count, room_id=room_id),
    )
    return {
        "following": following,
        "follower_count": count,
        "room_id": room_id,
    }


@app.get("/api/live-rooms/{room_id}/follow")
def live_room_follow_status(room_id: str, identity: str = "") -> dict:
    store = _live_rooms()
    try:
        store.require(room_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown live room")
    return {
        "following": store.is_following_host(room_id, identity),
        "follower_count": store.host_follower_count(room_id),
    }


@app.websocket("/api/live-rooms/{room_id}/ws")
async def live_room_websocket(room_id: str, websocket: WebSocket) -> None:
    store = _live_rooms()
    if store.get(room_id) is None:
        await websocket.close(code=4404)
        return
    hub = app.state.live_room_hub
    await hub.connect(room_id, websocket)
    from aoep_shared.live_room_ws import ws_room_snapshot  # noqa: E402

    try:
        room = store.require(room_id).to_dict()
        await websocket.send_json(ws_room_snapshot(room, room_id=room_id))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(room_id, websocket)


# --------------------------------------------------------------------------- #
# Scenario training agents (critical thinking, emergency drills)
# --------------------------------------------------------------------------- #
from .training import (  # noqa: E402
    CapacityResponse,
    CatalogMetaResponse,
    CreateTrainingSessionRequest,
    FamilySummary,
    GeneratedScenario,
    GrowthStatusResponse,
    KnowledgeListResponse,
    KnowledgeMetaResponse,
    KnowledgeStoreStatus,
    RespondRequest,
    RespondResponse,
    ScenarioListResponse,
    ScenarioSummary,
    TickResponse,
    TrackScenarioListResponse,
    TrackSummary,
    TrainingSessionView,
    agent_roster_dict,
    capacity_report,
    catalog_summary,
    create_training_session,
    generate_one,
    generate_random,
    get_full_scenario,
    get_training_session,
    growth_status,
    knowledge_meta_view,
    knowledge_search_view,
    knowledge_sources_view,
    knowledge_store_view,
    list_domain_counts,
    list_family_summaries,
    list_scenario_summaries,
    list_track_summaries,
    pick_random_scenario,
    respond_training_session,
    tick_training_session,
    track_scenarios,
    training_capabilities,
)


@app.get("/api/agents/roster")
def agents_roster() -> list[dict]:
    """Full platform agent roster: harvester, presenter, chatbot, training coaches."""
    return agent_roster_dict()


@app.get("/api/training/catalog", response_model=CatalogMetaResponse)
def training_catalog() -> CatalogMetaResponse:
    return catalog_summary()


@app.get("/api/training/capacity", response_model=CapacityResponse)
def training_capacity() -> CapacityResponse:
    """Total addressable scenarios: materialized + procedurally generable (millions)."""
    return capacity_report()


@app.get("/api/training/families", response_model=list[FamilySummary])
def training_families() -> list[FamilySummary]:
    return list_family_summaries()


@app.get("/api/training/generate", response_model=GeneratedScenario)
def training_generate(family_id: str, index: int = 0) -> GeneratedScenario:
    """Deterministically generate any scenario in a family by index."""
    gen = generate_one(family_id, index)
    if gen is None:
        raise HTTPException(status_code=404, detail="unknown family")
    return gen


@app.get("/api/training/generate/random", response_model=GeneratedScenario)
def training_generate_random(
    family_id: str | None = None, seed: int | None = None
) -> GeneratedScenario:
    gen = generate_random(family_id=family_id, seed=seed)
    if gen is None:
        raise HTTPException(status_code=404, detail="no scenario available")
    return gen


@app.get("/api/training/knowledge", response_model=KnowledgeListResponse)
def training_knowledge(
    q: str | None = None,
    domain: str | None = None,
    category: str | None = None,
    source: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> KnowledgeListResponse:
    """Browse the real, cited safety knowledge base grounding the scenarios."""
    return knowledge_search_view(
        q=q, domain=domain, category=category, source=source, offset=offset, limit=limit
    )


@app.get("/api/training/knowledge/meta", response_model=KnowledgeMetaResponse)
def training_knowledge_meta() -> KnowledgeMetaResponse:
    return knowledge_meta_view()


@app.get("/api/training/knowledge/sources")
def training_knowledge_sources() -> list[dict]:
    return knowledge_sources_view()


@app.get("/api/training/knowledge/status", response_model=KnowledgeStoreStatus)
def training_knowledge_status() -> KnowledgeStoreStatus:
    """Persistent embedded knowledge DB status (backend, path, FTS5, count)."""
    return knowledge_store_view()


@app.get("/api/training/growth", response_model=GrowthStatusResponse)
def training_growth() -> GrowthStatusResponse:
    """Aggregate growth metrics across knowledge, scenarios, slang, presentation, packs."""
    return growth_status()


@app.get("/api/training/capabilities")
def training_capabilities_endpoint() -> dict:
    """Unified directory of the consolidated training + cognitive agent suites."""
    return training_capabilities()


@app.get("/api/language/readability")
def language_readability(text: str, simplify_to: str | None = None) -> dict:
    """Score language complexity and optionally simplify toward a reading level."""
    from aoep_shared.readability import analyze, simplify_text

    out: dict = {"metrics": analyze(text).to_dict()}
    if simplify_to:
        simplified = simplify_text(text, reading_level=simplify_to)
        out["simplified"] = simplified
        out["simplified_metrics"] = analyze(simplified).to_dict()
    return out


@app.get("/api/presentation/techniques")
def presentation_techniques(category: str | None = None) -> list[dict]:
    """List AI presentation/teaching techniques (built-in + content packs)."""
    from aoep_shared.presentation_skills import list_techniques

    return [
        {"id": t.id, "name": t.name, "description": t.description,
         "category": t.category, "tags": list(t.tags)}
        for t in list_techniques(category=category)
    ]


class SkillPlanRequest(BaseModel):
    headings: list[str]
    topic: str = ""


@app.post("/api/presentation/skill-plan")
def presentation_skill_plan(req: SkillPlanRequest) -> list[dict]:
    """Assign varied presentation techniques across a deck for engaging delivery."""
    from aoep_shared.presentation_skills import build_skill_plan

    return build_skill_plan(req.headings, topic=req.topic)


@app.get("/api/training/domains")
def training_domains() -> list[dict]:
    return list_domain_counts()


@app.get("/api/training/scenarios", response_model=ScenarioListResponse)
def training_scenarios(
    domain: str | None = None,
    skill: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> ScenarioListResponse:
    return list_scenario_summaries(domain=domain, skill=skill, q=q, offset=offset, limit=limit)


@app.get("/api/training/scenarios/random", response_model=ScenarioSummary)
def training_scenario_random(
    domain: str | None = None,
    track_id: str | None = None,
    seed: int | None = None,
) -> ScenarioSummary:
    picked = pick_random_scenario(domain=domain, track_id=track_id, seed=seed)
    if picked is None:
        raise HTTPException(status_code=404, detail="no matching scenario")
    return picked


@app.get("/api/training/tracks", response_model=list[TrackSummary])
def training_tracks() -> list[TrackSummary]:
    return list_track_summaries()


@app.get("/api/training/tracks/{track_id}", response_model=TrackScenarioListResponse)
def training_track_scenarios(
    track_id: str,
    offset: int = 0,
    limit: int = 50,
) -> TrackScenarioListResponse:
    body = track_scenarios(track_id, offset=offset, limit=limit)
    if body is None:
        raise HTTPException(status_code=404, detail="unknown track")
    return body


@app.get("/api/training/scenarios/{scenario_id}", response_model=GeneratedScenario)
def training_scenario_detail(scenario_id: str) -> GeneratedScenario:
    """Full scenario (materialized or procedural) with real cited references."""
    full = get_full_scenario(scenario_id)
    if full is None:
        raise HTTPException(status_code=404, detail="unknown scenario")
    return full


@app.post("/api/training/sessions", response_model=TrainingSessionView)
def training_session_create(req: CreateTrainingSessionRequest) -> TrainingSessionView:
    try:
        session = create_training_session(req.scenario_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TrainingSessionView(**session.to_view())


@app.get("/api/training/sessions/{session_id}", response_model=TrainingSessionView)
def training_session_get(session_id: str) -> TrainingSessionView:
    session = get_training_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown training session")
    return TrainingSessionView(**session.to_view())


@app.post("/api/training/sessions/{session_id}/tick", response_model=TickResponse)
def training_session_tick(session_id: str) -> TickResponse:
    session, turns = tick_training_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown training session")
    from .training import _session_view, _turn_views

    return TickResponse(session=_session_view(session), turns=_turn_views(turns or []))


@app.post("/api/training/sessions/{session_id}/respond", response_model=RespondResponse)
def training_session_respond(session_id: str, req: RespondRequest) -> RespondResponse:
    session, turns = respond_training_session(session_id, req.text)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown training session")
    from .training import _session_view, _turn_views

    return RespondResponse(session=_session_view(session), turns=_turn_views(turns or []))


# ---------------------------------------------------------------------------
# Cognitive Training API
# ---------------------------------------------------------------------------
from aoep_shared.cognitive_trainer import (  # noqa: E402
    CognitiveLearnerProfile,
    CognitiveTrainer,
)

_cognitive_trainer = CognitiveTrainer()
_cognitive_profiles: _ODict[str, CognitiveLearnerProfile] = _ODict()
_MAX_COGNITIVE_PROFILES = 10_000


def _get_profile(learner_id: str) -> CognitiveLearnerProfile:
    if learner_id not in _cognitive_profiles:
        _cognitive_profiles[learner_id] = _cognitive_trainer.create_profile(learner_id)
        if len(_cognitive_profiles) > _MAX_COGNITIVE_PROFILES:
            _cognitive_profiles.popitem(last=False)  # evict oldest entry
    return _cognitive_profiles[learner_id]


class CognitiveCheckInRequest(BaseModel):
    learner_id: str
    stress_level: int = 5      # 1–10
    focus_level: int = 7       # 1–10
    wellness_state: str = "ok"


class CriticalThinkingRequest(BaseModel):
    learner_id: str
    term: str
    passage: str
    scenario: str = ""
    claim: str = ""


class CriticalThinkingEvalRequest(BaseModel):
    learner_id: str
    question_id: str
    question_text: str
    bloom_level: str
    acceptable_keywords: list[str] = []
    follow_up: str = ""
    challenge: str = ""
    hint: str = ""
    learner_answer: str


class SAScenarioRequest(BaseModel):
    learner_id: str
    scenario_id: str
    framework: str = "ooda"    # ooda | decide


class RapidDrillRequest(BaseModel):
    learner_id: str
    drill_id: str
    chosen_label: str
    time_taken_s: float
    pressure_level: str = "moderate"


class EmergencyScenarioRequest(BaseModel):
    learner_id: str
    scenario_id: str


class EmergencyActionRequest(BaseModel):
    learner_id: str
    scenario_id: str
    phase_id: str
    action_id: str
    time_taken_s: float = 0.0


class PreMortemRequest(BaseModel):
    learner_id: str
    plan_description: str
    failure_modes: list[str]


class RehearsalRequest(BaseModel):
    learner_id: str
    rehearsal_key: str


class TEMRequest(BaseModel):
    learner_id: str
    scenario_description: str
    learner_threats: list[str]


@app.post("/api/cognitive/check-in")
def cognitive_check_in(req: CognitiveCheckInRequest) -> dict:
    """Wellness and readiness check-in; returns grounding exercise if needed."""
    profile = _get_profile(req.learner_id)
    profile.wellness_state = req.wellness_state
    result = _cognitive_trainer.check_in(profile, req.stress_level, req.focus_level)
    return {
        "stress_level": result.stress_level,
        "focus_level": result.focus_level,
        "readiness_note": result.readiness_note,
        "recommended_exercise": result.recommended_exercise.value,
        "breath_cue": result.breath_cue,
    }


@app.get("/api/cognitive/recommend/{learner_id}")
def cognitive_recommend(learner_id: str) -> dict:
    """Return next recommended cognitive training activity for a learner."""
    profile = _get_profile(learner_id)
    return _cognitive_trainer.recommend_next_session(profile)


@app.get("/api/cognitive/summary/{learner_id}")
def cognitive_summary(learner_id: str) -> dict:
    """Return full cognitive training profile summary."""
    profile = _get_profile(learner_id)
    return _cognitive_trainer.adaptation_summary(profile)


@app.post("/api/cognitive/critical-thinking/question")
def critical_thinking_question(req: CriticalThinkingRequest) -> dict:
    """Generate the next Socratic question for a learner on a term/passage."""
    profile = _get_profile(req.learner_id)
    q = _cognitive_trainer.critical_thinking_question(
        profile, req.term, req.passage,
        scenario=req.scenario, claim=req.claim,
    )
    return {
        "question_id": q.question_id,
        "text": q.text,
        "bloom_level": q.bloom_level.value,
        "hint": q.hint,
        "acceptable_keywords": q.acceptable_keywords,
    }


@app.post("/api/cognitive/critical-thinking/evaluate")
def critical_thinking_evaluate(req: CriticalThinkingEvalRequest) -> dict:
    """Evaluate a learner's answer to a Socratic question."""
    from aoep_shared.critical_thinking import BloomLevel, SocraticQuestion
    profile = _get_profile(req.learner_id)
    try:
        bloom = BloomLevel(req.bloom_level)
    except ValueError:
        bloom = BloomLevel.UNDERSTAND
    question = SocraticQuestion(
        question_id=req.question_id,
        text=req.question_text,
        bloom_level=bloom,
        follow_up=req.follow_up,
        challenge=req.challenge,
        hint=req.hint,
        acceptable_keywords=req.acceptable_keywords,
    )
    result = _cognitive_trainer.critical_thinking_evaluate(profile, question, req.learner_answer)
    return {
        "score": result.score,
        "feedback": result.feedback,
        "keywords_found": result.keywords_found,
        "bloom_level": result.bloom_level.value,
        "reasoning_gap": result.reasoning_gap,
    }


@app.get("/api/cognitive/situational/scenarios")
def list_sa_scenarios(domain: str | None = None) -> dict:
    """List available situational awareness scenarios."""
    scenarios = _cognitive_trainer.sa_list_scenarios(domain)
    return {"scenarios": [
        {"id": s.scenario_id, "title": s.title, "domain": s.domain,
         "time_pressure_s": s.time_pressure_seconds}
        for s in scenarios
    ]}


@app.post("/api/cognitive/situational/ooda-prompt")
def sa_ooda_prompt(req: SAScenarioRequest) -> dict:
    """Return the OBSERVE phase prompt for an OODA scenario."""
    from aoep_shared.situational_awareness import OODAPhase
    profile = _get_profile(req.learner_id)
    prompt = _cognitive_trainer.sa_ooda_prompt(profile, req.scenario_id, OODAPhase.OBSERVE)
    return {"prompt": prompt, "phase": "observe", "scenario_id": req.scenario_id}


@app.get("/api/cognitive/rapid-decision/drills")
def list_rd_drills(domain: str | None = None) -> dict:
    """List available rapid-decision drills."""
    drills = _cognitive_trainer.rapid_decision.list_drills(domain)
    return {"drills": [
        {"id": d.drill_id, "domain": d.domain, "skill_tag": d.skill_tag,
         "ideal_seconds": d.ideal_seconds, "situation": d.situation[:120]}
        for d in drills
    ]}


@app.post("/api/cognitive/rapid-decision/evaluate")
def rd_evaluate(req: RapidDrillRequest) -> dict:
    """Evaluate a learner's rapid-decision drill attempt."""
    from aoep_shared.rapid_decision import PressureLevel as PL
    profile = _get_profile(req.learner_id)
    try:
        pressure = PL(req.pressure_level)
    except ValueError:
        pressure = PL.MODERATE
    result = _cognitive_trainer.rd_evaluate(
        profile, req.drill_id, req.chosen_label,
        req.time_taken_s, pressure,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"drill {req.drill_id!r} not found")
    return {
        "outcome": result.outcome.value,
        "feedback": result.feedback,
        "adr": result.adr,
        "cue_spotlight": result.cue_spotlight,
        "correct_option": result.correct_option_label,
        "time_taken_s": result.time_taken_s,
        "allowed_seconds": result.allowed_seconds,
    }


@app.get("/api/cognitive/emergency/scenarios")
def list_emergency_scenarios(domain: str | None = None) -> dict:
    """List available emergency simulation scenarios."""
    from aoep_shared.emergency_scenarios import ScenarioDomain as SD
    dom = None
    if domain:
        try:
            dom = SD(domain)
        except ValueError:
            pass
    scenarios = _cognitive_trainer.em_list_scenarios(dom)
    return {"scenarios": [
        {"id": s.scenario_id, "title": s.title, "domain": s.domain.value,
         "difficulty": s.difficulty,
         "objectives": s.learning_objectives}
        for s in scenarios
    ]}


@app.post("/api/cognitive/emergency/start")
def emergency_start(req: EmergencyScenarioRequest) -> dict:
    """Start an emergency scenario simulation run."""
    profile = _get_profile(req.learner_id)
    run = _cognitive_trainer.em_start(profile, req.scenario_id)
    if run is None:
        if profile.wellness_state in ("stressed", "unwell"):
            raise HTTPException(
                status_code=409,
                detail="Emergency simulation unavailable: learner wellness check required first",
            )
        raise HTTPException(status_code=404, detail=f"scenario {req.scenario_id!r} not found")
    scenario = _cognitive_trainer.emergency.get_scenario(req.scenario_id)
    phase = _cognitive_trainer.emergency.current_phase(run, scenario)
    prompt = _cognitive_trainer.emergency.phase_prompt(phase)
    return {
        "scenario_id": run.scenario_id,
        "learner_id": run.learner_id,
        "current_phase": phase.phase_id,
        "prompt": prompt,
        "status": run.status.value,
    }


@app.post("/api/cognitive/emergency/action")
def emergency_action(req: EmergencyActionRequest) -> dict:
    """Apply a learner's action in an emergency scenario."""
    profile = _get_profile(req.learner_id)
    scenario = _cognitive_trainer.emergency.get_scenario(req.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario not found")

    # Reconstruct run from single-shot (stateless demo mode)
    run = _cognitive_trainer.em_start(profile, req.scenario_id)
    if run is None:
        raise HTTPException(status_code=409, detail="simulation blocked by wellness gate")
    run.current_phase_id = req.phase_id

    phase = scenario.get_phase(req.phase_id)
    if not phase:
        raise HTTPException(status_code=404, detail="phase not found")

    action = _cognitive_trainer.emergency.apply_action(
        run, phase, req.action_id, req.time_taken_s or None
    )
    if action is None:
        raise HTTPException(status_code=400, detail=f"action {req.action_id!r} not found in phase")

    response: dict = {
        "action_id": action.action_id,
        "outcome": action.outcome.value,
        "consequence": action.consequence,
        "status": run.status.value,
    }

    if run.status.value in ("completed", "terminated_early"):
        aar = _cognitive_trainer.em_aar(profile, run)
        if aar:
            response["aar"] = {
                "outcome_score": aar.outcome_score,
                "overall_verdict": aar.overall_verdict,
                "decisions_summary": aar.decisions_summary,
                "expert_comparison": aar.expert_comparison,
                "learning_reinforcements": aar.learning_reinforcements,
            }
    else:
        next_phase = scenario.get_phase(run.current_phase_id)
        if next_phase:
            response["next_phase"] = next_phase.phase_id
            response["next_prompt"] = _cognitive_trainer.emergency.phase_prompt(next_phase)

    return response


@app.post("/api/cognitive/mental-readiness/pre-mortem")
def mental_readiness_pre_mortem(req: PreMortemRequest) -> dict:
    """Run a pre-mortem exercise on a plan."""
    profile = _get_profile(req.learner_id)
    result = _cognitive_trainer.readiness_pre_mortem(
        profile, req.plan_description, req.failure_modes
    )
    return {
        "plan": result.plan_description,
        "failure_modes": result.failure_modes,
        "mitigations": result.mitigations,
        "residual_risks": result.residual_risks,
        "confidence_adjustment": result.confidence_adjustment,
    }


@app.post("/api/cognitive/mental-readiness/rehearsal")
def mental_readiness_rehearsal(req: RehearsalRequest) -> dict:
    """Return a formatted mental rehearsal script."""
    profile = _get_profile(req.learner_id)
    text = _cognitive_trainer.readiness_rehearsal(profile, req.rehearsal_key)
    available = _cognitive_trainer.mental_readiness.list_rehearsal_keys()
    return {"rehearsal_key": req.rehearsal_key, "text": text, "available_keys": available}


@app.post("/api/cognitive/mental-readiness/tem")
def mental_readiness_tem(req: TEMRequest) -> dict:
    """Threat and Error Management analysis."""
    profile = _get_profile(req.learner_id)
    result = _cognitive_trainer.readiness_tem(
        profile, req.scenario_description, req.learner_threats
    )
    return {
        "threats_identified": [
            {"category": t.category.value, "description": t.description,
             "countermeasure": t.countermeasure}
            for t in result.threats_identified
        ],
        "undetected_threats": result.undetected_threats,
        "error_traps": result.error_traps,
        "feedback": result.feedback,
    }
