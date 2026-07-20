"""Server-authoritative course assessment, presentation, and retention policy."""

from __future__ import annotations

import enum
import time
import uuid
from typing import Dict, Iterable, List, Sequence

from pydantic import BaseModel, Field

from .assessment import QuizItem
from .catalog_selection import profile_dimensions


class AssessmentStage(str, enum.Enum):
    FORMATIVE = "formative"
    SUMMATIVE = "summative"
    RETENTION = "retention"


class AssessmentFormat(str, enum.Enum):
    AUTO = "auto"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO_AID = "video_aid"
    GAME = "game"


class EvidenceDomain(str, enum.Enum):
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    BEHAVIOUR = "behaviour"


class CheckpointPolicy(BaseModel):
    checkpoint_id: str
    stage: AssessmentStage = AssessmentStage.FORMATIVE
    pass_threshold: float = 0.7
    min_items: int = Field(default=3, ge=1)
    max_attempts: int = 3
    required: bool = True
    ksb_coverage_min: float = 0.0
    required_domains: List[EvidenceDomain] = Field(
        default_factory=lambda: [EvidenceDomain.KNOWLEDGE],
    )


class ItemEvidence(BaseModel):
    item_id: str
    correct: bool
    chosen_index: int
    evidence_domain: EvidenceDomain = EvidenceDomain.KNOWLEDGE
    ksb_codes: List[str] = Field(default_factory=list)


class AssessmentAttemptResult(BaseModel):
    attempt_id: str = Field(default_factory=lambda: f"attempt-{uuid.uuid4().hex[:16]}")
    student_id: str
    course_id: str
    checkpoint_id: str
    stage: AssessmentStage
    presentation_format: AssessmentFormat
    score: float
    passed: bool
    item_evidence: List[ItemEvidence] = Field(default_factory=list)
    ksb_coverage: float = 0.0
    domains_evidenced: List[EvidenceDomain] = Field(default_factory=list)
    attempt_number: int = 1
    submitted_at: float = Field(default_factory=time.time)


class CoursePassDecision(BaseModel):
    student_id: str
    course_id: str
    passed: bool
    score: float
    reason: str
    attempt_ids: List[str] = Field(default_factory=list)
    ksb_codes_evidenced: List[str] = Field(default_factory=list)
    decided_at: float = Field(default_factory=time.time)


class RetentionCheck(BaseModel):
    check_id: str = Field(default_factory=lambda: f"retain-{uuid.uuid4().hex[:16]}")
    student_id: str
    course_id: str
    interval_days: int
    due_at: float
    status: str = "pending"
    source_attempt_id: str = ""
    completed_attempt_id: str = ""
    score: float | None = None


def select_assessment_format(
    profile_score: str = "",
    *,
    requested: str = "auto",
    primary_style: str = "",
    device_mode: str = "class",
    needs_captions: bool = False,
    uses_assistive_tech: bool = False,
) -> AssessmentFormat:
    """Choose presentation only; every format uses the same canonical answer key."""
    if requested and requested != AssessmentFormat.AUTO.value:
        try:
            selected = AssessmentFormat(requested)
        except ValueError as exc:
            raise ValueError(f"unsupported assessment format: {requested}") from exc
    else:
        dimensions = profile_dimensions(
            profile_score, primary_style=primary_style,
        )
        style = dimensions.get("primary_style", primary_style or "mixed")
        selected = {
            "visual": AssessmentFormat.VIDEO_AID,
            "auditory": AssessmentFormat.AUDIO,
            "reading_writing": AssessmentFormat.TEXT,
            "hands_on": AssessmentFormat.GAME,
            "mixed": AssessmentFormat.TEXT,
        }.get(style, AssessmentFormat.TEXT)
    # Apply accessibility overrides before device-mode forcing so caption-
    # dependent learners always get text even in drive mode.
    if needs_captions and selected == AssessmentFormat.AUDIO:
        selected = AssessmentFormat.TEXT
    if uses_assistive_tech and selected in {AssessmentFormat.VIDEO_AID, AssessmentFormat.GAME}:
        selected = AssessmentFormat.TEXT
    if device_mode == "drive":
        return AssessmentFormat.AUDIO if not needs_captions else AssessmentFormat.TEXT
    return selected


def present_item(item: QuizItem, presentation_format: AssessmentFormat) -> dict:
    """Return an answer-safe view of a canonical item for one presentation shell."""
    base = {
        "item_id": item.item_id,
        "topic": item.topic,
        "prompt": item.prompt,
        "options": list(item.options),
        "difficulty": item.difficulty.value,
        "format": presentation_format.value,
    }
    if presentation_format == AssessmentFormat.AUDIO:
        base["audio"] = {
            "narration": f"{item.prompt} " + " ".join(
                f"Option {index + 1}: {option}."
                for index, option in enumerate(item.options)
            ),
            "transcript": True,
        }
    elif presentation_format == AssessmentFormat.VIDEO_AID:
        base["video_aid"] = {
            "presenter_cue": item.prompt,
            "captions": True,
            "visual_prompt": item.topic,
        }
    elif presentation_format == AssessmentFormat.GAME:
        base["game"] = {
            "kind": "knowledge_challenge",
            "content_id": item.item_id,
            "timed": False,
            "points_per_correct": 100,
        }
    return base


def evaluate_checkpoint(
    *,
    student_id: str,
    course_id: str,
    policy: CheckpointPolicy,
    items: Sequence[QuizItem],
    chosen_indices: Sequence[int],
    presentation_format: AssessmentFormat,
    attempt_number: int = 1,
    ksb_by_item: Dict[str, List[str]] | None = None,
    domain_by_item: Dict[str, EvidenceDomain] | None = None,
) -> AssessmentAttemptResult:
    """Grade one checkpoint and enforce threshold, KSB coverage, and domains."""
    if attempt_number > policy.max_attempts:
        raise ValueError("maximum checkpoint attempts exceeded")
    if len(items) < policy.min_items:
        raise ValueError("checkpoint does not contain enough assessment items")
    if len(chosen_indices) != len(items):
        raise ValueError("one answer is required for every assessment item")

    ksb_by_item = ksb_by_item or {}
    domain_by_item = domain_by_item or {}
    evidence: List[ItemEvidence] = []
    all_ksbs = {code for codes in ksb_by_item.values() for code in codes}
    evidenced_ksbs: set[str] = set()
    domains: set[EvidenceDomain] = set()
    correct_count = 0
    for item, chosen in zip(items, chosen_indices):
        correct = int(chosen) == item.answer_index
        domain = domain_by_item.get(item.item_id, EvidenceDomain.KNOWLEDGE)
        codes = list(ksb_by_item.get(item.item_id, []))
        if correct:
            correct_count += 1
            evidenced_ksbs.update(codes)
            domains.add(domain)
        evidence.append(ItemEvidence(
            item_id=item.item_id,
            correct=correct,
            chosen_index=int(chosen),
            evidence_domain=domain,
            ksb_codes=codes,
        ))

    score = correct_count / len(items)
    coverage = len(evidenced_ksbs) / len(all_ksbs) if all_ksbs else 1.0
    domains_ok = set(policy.required_domains).issubset(domains)
    passed = (
        score >= policy.pass_threshold
        and coverage >= policy.ksb_coverage_min
        and domains_ok
    )
    return AssessmentAttemptResult(
        student_id=student_id,
        course_id=course_id,
        checkpoint_id=policy.checkpoint_id,
        stage=policy.stage,
        presentation_format=presentation_format,
        score=round(score, 4),
        passed=passed,
        item_evidence=evidence,
        ksb_coverage=round(coverage, 4),
        domains_evidenced=sorted(domains, key=lambda domain: domain.value),
        attempt_number=attempt_number,
    )


def decide_course_pass(
    student_id: str,
    course_id: str,
    attempts: Iterable[AssessmentAttemptResult],
) -> CoursePassDecision:
    """Require a passing summative attempt; formative work alone cannot pass."""
    relevant = [
        attempt for attempt in attempts
        if attempt.student_id == student_id and attempt.course_id == course_id
    ]
    summative = [
        attempt for attempt in relevant
        if attempt.stage == AssessmentStage.SUMMATIVE
    ]
    passed = [attempt for attempt in summative if attempt.passed]
    if not passed:
        return CoursePassDecision(
            student_id=student_id,
            course_id=course_id,
            passed=False,
            score=max((attempt.score for attempt in summative), default=0.0),
            reason="a passing summative assessment is required",
            attempt_ids=[attempt.attempt_id for attempt in summative],
        )
    best = max(passed, key=lambda attempt: attempt.score)
    codes = {
        code
        for item in best.item_evidence
        if item.correct
        for code in item.ksb_codes
    }
    return CoursePassDecision(
        student_id=student_id,
        course_id=course_id,
        passed=True,
        score=best.score,
        reason="summative policy satisfied",
        attempt_ids=[attempt.attempt_id for attempt in relevant],
        ksb_codes_evidenced=sorted(codes),
    )


def schedule_retention_checks(
    *,
    student_id: str,
    course_id: str,
    completed_at: float,
    source_attempt_id: str,
    intervals_days: Sequence[int] = (1, 7, 30, 90),
) -> List[RetentionCheck]:
    """Build spaced-retrieval checks from one verified pass.

    The first interval is 1 day (not 0) so no check is immediately due at the
    moment of course completion — a due_at == completed_at check would be
    permanently overdue from the instant it is created.
    """
    return [
        RetentionCheck(
            student_id=student_id,
            course_id=course_id,
            interval_days=int(days),
            due_at=completed_at + (int(days) * 86_400),
            source_attempt_id=source_attempt_id,
        )
        for days in intervals_days
    ]
