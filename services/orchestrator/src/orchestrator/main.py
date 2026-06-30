"""Orchestrator FastAPI app.

Owns class-session lifecycle and exposes the Director decision endpoint. It
issues LiveKit join tokens via the MediaProvider so the same flow works against a
local LiveKit container or a cloud cluster.
"""

from __future__ import annotations

import uuid

from aoep_shared.adaptive import AdaptivePolicy, Difficulty, LearnerSignals, Pacing
from aoep_shared.assessment import (
    GradeResult,
    QuizItem,
    definition_items_from_passages,
    grade,
)
from aoep_shared.internal_auth import require_internal
from aoep_shared.schemas import ClassType
from aoep_shared.service import create_service
from fastapi import Depends, HTTPException, Response
from pydantic import BaseModel

from .curriculum import CourseKSB, Lesson, Slide
from .director import ClassContext, Director, LessonState
from .teaching import Answer, Reengagement, SessionView, TeachingSessions

app = create_service("orchestrator")

from aoep_shared.optimization import OptimizationLedger  # noqa: E402

app.state.optimization = OptimizationLedger()

import os  # noqa: E402

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


def get_sessions() -> TeachingSessions:
    global _sessions
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


class AskRequest(BaseModel):
    text: str
    language: str = "en"


@app.get("/api/lessons", response_model=list[Lesson])
def api_lessons() -> list[Lesson]:
    return get_sessions().list_lessons()


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


@app.post("/api/sessions", response_model=SessionView)
def api_start_session(req: StartSessionRequest) -> SessionView:
    sessions = get_sessions()
    try:
        state = sessions.start_session(
            req.lesson_id, req.class_type.value, student_id=req.student_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {req.lesson_id}")
    return SessionView(
        session=state,
        lesson=sessions.lesson_for(state.session_id),
        slide=sessions.current_slide(state.session_id),
    )


@app.get("/api/sessions/{session_id}", response_model=SessionView)
def api_get_session(session_id: str) -> SessionView:
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


_AGENT_REWARD_POINTS = int(os.environ.get("AGENT_REWARD_POINTS", "10"))
_AGENT_REWARD_SESSION_CAP = int(os.environ.get("AGENT_REWARD_SESSION_CAP", "30"))
_session_reward_total: dict[str, int] = {}


def _maybe_grant_reward(session_id: str, question: str, answer: Answer) -> None:
    key = os.environ.get("INTERNAL_TOKEN_KEY", "")
    if not key or not answer.grounded or answer.pending_review:
        return
    if len(question.strip()) < 12:   # ignore trivial/empty questions
        return
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
    answer_index: int
    difficulty: Difficulty


class QuizResponse(BaseModel):
    items: list[QuizItemView]


class GradeRequest(BaseModel):
    item_id: str
    options: list[str]
    answer_index: int
    chosen_index: int
    difficulty: Difficulty = Difficulty.MEDIUM
    topic: str = ""
    # When set, the outcome updates the learner's mastery in the memory service,
    # closing the loop so the next quiz adapts its difficulty.
    student_id: str | None = None


class GradeResponse(BaseModel):
    item_id: str
    correct: bool
    mastery_target: float
    difficulty: Difficulty


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
    return QuizResponse(
        items=[
            QuizItemView(
                item_id=i.item_id,
                topic=i.topic,
                prompt=i.prompt,
                options=i.options,
                answer_index=i.answer_index,
                difficulty=i.difficulty,
            )
            for i in items
        ]
    )


@app.post("/assessment/grade", response_model=GradeResponse)
def assessment_grade(req: GradeRequest) -> GradeResponse:
    item = QuizItem(
        item_id=req.item_id,
        topic=req.topic,
        prompt="",
        options=req.options,
        answer_index=req.answer_index,
        difficulty=req.difficulty,
    )
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
    ClassFullError,
    GroupClassError,
    GroupClassStore,
    bridge_plan,
)

app.state.group_classes = GroupClassStore()


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


@app.on_event("startup")
def _orchestrator_startup() -> None:
    _seed_group_classes()


def _group_store() -> GroupClassStore:
    return app.state.group_classes


class ScheduleGroupClassRequest(BaseModel):
    title: str
    lesson_id: str
    start_time: str
    platform: str = "salareen"
    meeting_url: str = ""
    duration_min: int = 60
    host: str = "Salareen AI"
    capacity: int = 100
    language: str = "en"
    description: str = ""


class RegisterRequest(BaseModel):
    name: str
    email: str = ""


@app.get("/api/group-classes")
def list_group_classes(upcoming: bool = True) -> dict:
    from aoep_shared.group_classes import ensure_standard_daily_classes

    ensure_standard_daily_classes(_group_store())
    classes = _group_store().list(upcoming_only=upcoming)
    return {"classes": [c.to_dict() for c in classes]}


@app.post("/api/group-classes")
def schedule_group_class(req: ScheduleGroupClassRequest) -> dict:
    try:
        gc = _group_store().schedule(**req.model_dump())
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return gc.to_dict()


@app.get("/api/group-classes/{class_id}")
def get_group_class(class_id: str) -> dict:
    gc = _group_store().get(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")
    return gc.to_dict()


@app.post("/api/group-classes/{class_id}/register")
def register_group_class(class_id: str, req: RegisterRequest) -> dict:
    store = _group_store()
    try:
        store.register(class_id, req.name, req.email)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown group class")
    except ClassFullError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except GroupClassError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return store.require(class_id).to_dict()


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
def start_group_class(class_id: str) -> dict:  # noqa: F811 (overrides nothing)
    """Go live: create the teaching session and return the meeting bridge plan.

    The AI's coursework runs as a normal teaching session; the returned
    ``bridge`` describes how to pipe its LiveKit room into the scheduled
    meeting (Zoom/Teams/Meet) so the AI presents through that platform. For
    built-in "salareen" classes, learners join the live room directly.
    """
    store = _group_store()
    gc = store.get(class_id)
    if gc is None:
        raise HTTPException(status_code=404, detail="unknown group class")

    sessions = get_sessions()
    try:
        state = sessions.start_session(gc.lesson_id, "group")
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown lesson {gc.lesson_id}")

    gc.session_id = state.session_id
    store.set_status(gc.id, "live")

    room = f"class-{gc.id}"
    plan = dict(bridge_plan(gc, livekit_room=room))
    media = app.state.factory.media()
    token = media.issue_token(room=room, identity="aoep-teacher")
    plan["livekit"] = {"room": token.room, "token": token.token, "url": token.url}

    return {
        "class": gc.to_dict(),
        "session": SessionView(
            session=state,
            lesson=sessions.lesson_for(state.session_id),
            slide=sessions.current_slide(state.session_id),
        ).model_dump(),
        "bridge": plan,
    }


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


@app.get("/api/presenter")
def presenter_profile(category: str | None = None, source: str | None = None) -> dict:
    """Theodore, the AI presenter: persona + the teaching-strategy playbook
    back-propagated from top online instructors (Tao, MasterClass, Musk + MOOC
    pedagogy). Optionally filter strategies by ``category`` or ``source``."""
    from aoep_shared import theodore

    out = theodore.persona()
    out["strategies"] = [
        {"id": s.id, "name": s.name, "category": s.category, "source": s.source,
         "principle": s.principle, "cue": s.cue}
        for s in theodore.list_strategies(category=category, source=source)
    ]
    return out


class RehearseRequest(BaseModel):
    narration: str
    topic: str = ""
    point: str = ""
    passes: int = 2


@app.post("/api/presenter/rehearse")
def presenter_rehearse(req: RehearseRequest) -> dict:
    """Rehearse a narration as Theodore: score it across delivery dimensions and
    iteratively embed the missing strategies, returning the improved take."""
    from aoep_shared import theodore

    result = theodore.rehearse(req.narration, topic=req.topic, point=req.point,
                               passes=max(1, min(5, req.passes)))
    return result.to_dict()


class PlaybookRequest(BaseModel):
    segment_kind: str = "segment"   # intro | segment | outro
    topic: str = ""
    point: str = ""


@app.post("/api/presenter/playbook")
def presenter_playbook(req: PlaybookRequest) -> dict:
    """The ordered strategy arc Theodore uses for a given segment kind."""
    from aoep_shared import theodore

    return {
        "segment_kind": req.segment_kind,
        "steps": theodore.delivery_playbook(
            segment_kind=req.segment_kind, topic=req.topic, point=req.point),
    }


@app.get("/api/presenter/attention")
def presenter_attention(score: float, topic: str = "") -> dict:
    """Given a learner attention score (0..1), the re-engagement strategies
    Theodore reaches for (pattern-interrupts when attention drops)."""
    from aoep_shared import theodore

    return theodore.adapt_for_attention(score, topic=topic)


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
_cognitive_profiles: dict[str, CognitiveLearnerProfile] = {}


def _get_profile(learner_id: str) -> CognitiveLearnerProfile:
    if learner_id not in _cognitive_profiles:
        _cognitive_profiles[learner_id] = _cognitive_trainer.create_profile(learner_id)
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
