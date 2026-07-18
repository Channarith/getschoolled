"""Shared XR lab assessment contract (WebXR + Unity OpenXR / Quest).

Normalized observations are scored server-side against a deterministic rubric.
Raw video and full motion streams are never accepted or persisted — only bounded
action summaries (controller/hand pose samples, step ids, timings).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


XR_PROTOCOL_VERSION = "aoep.xr.v1"
MAX_OBSERVATIONS_PER_ATTEMPT = 120
MAX_PAYLOAD_KEYS = 16


class XrOutcome(str, Enum):
    PASS = "pass"
    NEEDS_WORK = "needs_work"
    IN_PROGRESS = "in_progress"
    ABORTED = "aborted"


class XrClientKind(str, Enum):
    WEBXR = "webxr"
    UNITY_OPENXR = "unity_openxr"
    FALLBACK = "fallback"


@dataclass
class XrRubricStep:
    step_id: str
    title: str
    description: str = ""
    required_action: str = ""  # e.g. "grab", "place", "point", "confirm"
    target_id: str = ""
    min_hold_ms: int = 0
    weight: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class XrLabDefinition:
    lab_id: str
    title: str
    course_id: str = ""
    lesson_id: str = ""
    protocol_version: str = XR_PROTOCOL_VERSION
    pass_threshold: float = 0.7
    provisional: bool = True
    steps: List[XrRubricStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "lab_id": self.lab_id,
            "title": self.title,
            "course_id": self.course_id,
            "lesson_id": self.lesson_id,
            "protocol_version": self.protocol_version,
            "pass_threshold": self.pass_threshold,
            "provisional": self.provisional,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class XrObservation:
    """One normalized action sample from a headset client."""

    seq: int
    action: str
    target_id: str = ""
    hand: str = ""  # left | right | none
    confidence: float = 1.0
    hold_ms: int = 0
    ts_ms: int = 0
    # Bounded numeric pose summary only (no raw frames).
    pose: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "seq": int(self.seq),
            "action": (self.action or "").strip().lower(),
            "target_id": (self.target_id or "").strip(),
            "hand": (self.hand or "").strip().lower(),
            "confidence": round(max(0.0, min(1.0, float(self.confidence))), 3),
            "hold_ms": max(0, int(self.hold_ms)),
            "ts_ms": int(self.ts_ms or 0),
            "pose": {k: float(v) for k, v in list((self.pose or {}).items())[:8]},
        }


def observation_from_dict(raw: Dict[str, Any]) -> XrObservation:
    pose_raw = raw.get("pose") or {}
    pose: Dict[str, float] = {}
    if isinstance(pose_raw, dict):
        for i, (k, v) in enumerate(pose_raw.items()):
            if i >= 8:
                break
            try:
                pose[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    return XrObservation(
        seq=int(raw.get("seq") or 0),
        action=str(raw.get("action") or ""),
        target_id=str(raw.get("target_id") or ""),
        hand=str(raw.get("hand") or ""),
        confidence=float(raw.get("confidence") if raw.get("confidence") is not None else 1.0),
        hold_ms=int(raw.get("hold_ms") or 0),
        ts_ms=int(raw.get("ts_ms") or 0),
        pose=pose,
    )


@dataclass
class XrStepResult:
    step_id: str
    ok: bool
    score: float
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class XrAttemptResult:
    attempt_id: str
    lab_id: str
    student_id: str
    room_id: str
    client_kind: str
    outcome: str
    score: float
    provisional: bool
    step_results: List[XrStepResult] = field(default_factory=list)
    evidence_summary: str = ""
    protocol_version: str = XR_PROTOCOL_VERSION
    completed_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "lab_id": self.lab_id,
            "student_id": self.student_id,
            "room_id": self.room_id,
            "client_kind": self.client_kind,
            "outcome": self.outcome,
            "score": round(float(self.score), 3),
            "provisional": bool(self.provisional),
            "step_results": [s.to_dict() for s in self.step_results],
            "evidence_summary": self.evidence_summary,
            "protocol_version": self.protocol_version,
            "completed_at": self.completed_at,
        }


def default_lab_for_lesson(
    *,
    lesson_id: str = "",
    course_id: str = "",
    title: str = "Demonstrate the learned action",
) -> XrLabDefinition:
    """Baseline 3-step physical demonstration rubric for MVP labs."""
    lid = f"lab-{(lesson_id or course_id or 'demo')[:24]}"
    return XrLabDefinition(
        lab_id=lid,
        title=title or "Demonstrate the learned action",
        course_id=course_id,
        lesson_id=lesson_id,
        steps=[
            XrRubricStep(
                step_id="approach",
                title="Approach the work area",
                description="Move toward the labeled station",
                required_action="approach",
                target_id="station",
                weight=1.0,
            ),
            XrRubricStep(
                step_id="perform",
                title="Perform the key action",
                description="Grab or activate the primary tool/object",
                required_action="grab",
                target_id="tool",
                min_hold_ms=400,
                weight=2.0,
            ),
            XrRubricStep(
                step_id="confirm",
                title="Confirm completion",
                description="Place or confirm the finished action",
                required_action="confirm",
                target_id="finish",
                weight=1.0,
            ),
        ],
    )


def score_attempt(
    lab: XrLabDefinition,
    observations: List[XrObservation],
    *,
    student_id: str = "",
    room_id: str = "",
    client_kind: str = XrClientKind.WEBXR.value,
    attempt_id: str = "",
) -> XrAttemptResult:
    """Deterministic rubric scorer shared by WebXR and Unity clients."""
    obs = _normalize_observations(observations)
    step_results: List[XrStepResult] = []
    total_w = 0.0
    earned = 0.0
    for step in lab.steps:
        ok, score, evidence = _match_step(step, obs)
        step_results.append(
            XrStepResult(step_id=step.step_id, ok=ok, score=score, evidence=evidence)
        )
        w = max(0.0, float(step.weight))
        total_w += w
        earned += w * score
    ratio = (earned / total_w) if total_w > 0 else 0.0
    threshold = float(lab.pass_threshold)
    if not obs:
        outcome = XrOutcome.NEEDS_WORK.value
    elif ratio >= threshold:
        outcome = XrOutcome.PASS.value
    else:
        outcome = XrOutcome.NEEDS_WORK.value
    passed = sum(1 for s in step_results if s.ok)
    evidence_summary = (
        f"{passed}/{len(step_results)} steps ok; score={ratio:.2f} "
        f"(threshold={threshold:.2f}); client={client_kind}; provisional={lab.provisional}"
    )
    return XrAttemptResult(
        attempt_id=attempt_id or uuid.uuid4().hex[:12],
        lab_id=lab.lab_id,
        student_id=student_id,
        room_id=room_id,
        client_kind=client_kind,
        outcome=outcome,
        score=ratio,
        provisional=bool(lab.provisional),
        step_results=step_results,
        evidence_summary=evidence_summary,
    )


def _normalize_observations(raw: List[XrObservation]) -> List[XrObservation]:
    cleaned: List[XrObservation] = []
    for item in raw[:MAX_OBSERVATIONS_PER_ATTEMPT]:
        if not isinstance(item, XrObservation):
            if isinstance(item, dict):
                item = observation_from_dict(item)
            else:
                continue
        d = item.to_dict()
        if not d["action"]:
            continue
        cleaned.append(observation_from_dict(d))
    cleaned.sort(key=lambda o: (o.seq, o.ts_ms))
    # Drop out-of-order duplicates by seq (keep first).
    seen: set[int] = set()
    ordered: List[XrObservation] = []
    for o in cleaned:
        if o.seq in seen and o.seq > 0:
            continue
        if o.seq > 0:
            seen.add(o.seq)
        ordered.append(o)
    return ordered


def _match_step(
    step: XrRubricStep, observations: List[XrObservation]
) -> Tuple[bool, float, str]:
    action = (step.required_action or "").strip().lower()
    target = (step.target_id or "").strip()
    best: Optional[XrObservation] = None
    for o in observations:
        if action and o.action != action and o.action not in (action, f"{action}_ok"):
            # Allow synonyms for MVP: place ~= confirm for finish steps.
            if not _action_matches(o.action, action):
                continue
        if target and o.target_id and o.target_id != target:
            continue
        if step.min_hold_ms and o.hold_ms < step.min_hold_ms:
            continue
        if o.confidence < 0.35:
            continue
        best = o
        break
    if best is None:
        return False, 0.0, f"missing action={action or '*'} target={target or '*'}"
    score = 0.55 + 0.45 * best.confidence
    if step.min_hold_ms and best.hold_ms >= step.min_hold_ms:
        score = min(1.0, score + 0.1)
    return True, round(min(1.0, score), 3), f"matched seq={best.seq} action={best.action}"


def _action_matches(observed: str, required: str) -> bool:
    aliases = {
        "confirm": {"confirm", "place", "complete", "done"},
        "grab": {"grab", "grasp", "pickup", "hold"},
        "approach": {"approach", "move", "arrive", "near"},
        "point": {"point", "select", "aim"},
    }
    obs = (observed or "").lower()
    req = (required or "").lower()
    if obs == req:
        return True
    return obs in aliases.get(req, {req})


@dataclass
class XrLabState:
    """Per-room lab progress (privacy-safe public snapshot)."""

    enabled: bool = False
    lab: Optional[XrLabDefinition] = None
    attempts: Dict[str, dict] = field(default_factory=dict)  # participant_id -> summary

    def public_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "lab": self.lab.to_dict() if self.lab else None,
            "attempts": {
                pid: {
                    "outcome": row.get("outcome"),
                    "score": row.get("score"),
                    "provisional": row.get("provisional", True),
                    "client_kind": row.get("client_kind"),
                    "completed_at": row.get("completed_at"),
                }
                for pid, row in self.attempts.items()
            },
        }
