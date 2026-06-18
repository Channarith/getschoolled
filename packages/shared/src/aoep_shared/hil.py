"""Human-in-the-Loop (HIL) core - co-teaching / co-grading (Phase 10).

The AI proposes; a human approves / edits / rejects / takes over. Per-class or
per-assignment autonomy plus an escalation policy that auto-routes risky cases
to a human:
- HUMAN_LED  -> everything goes to a human.
- SUGGEST    -> co-pilot: a human approves every AI action.
- AUTONOMOUS -> deliver directly UNLESS escalation fires (low groundedness/high
  hallucination risk, low confidence, a sensitive subject, or a student request).

Pure/serializable + offline-testable; services hold a ReviewQueue and gate AI
actions through it (Phases 11-12). Overrides feed the corrections back-prop loop
and the optimization ledger.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

SENSITIVE_SUBJECTS = {"medical", "health", "legal", "law", "mental_health", "finance"}


class AutonomyLevel(str, enum.Enum):
    AUTONOMOUS = "autonomous"
    SUGGEST = "suggest"
    HUMAN_LED = "human_led"


class ReviewKind(str, enum.Enum):
    ANSWER = "answer"
    SLIDE = "slide"
    GRADE = "grade"


class ReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    TAKEN_OVER = "taken_over"


def should_escalate(
    *,
    autonomy: AutonomyLevel,
    risk: float = 0.0,
    ai_confidence: float = 1.0,
    subject: Optional[str] = None,
    student_requested: bool = False,
    risk_threshold: float = 0.3,
    confidence_threshold: float = 0.5,
) -> bool:
    """Whether an AI action must be routed to a human before delivery."""
    if autonomy is AutonomyLevel.HUMAN_LED:
        return True
    if autonomy is AutonomyLevel.SUGGEST:
        return True
    # AUTONOMOUS: only escalate on a concrete trigger.
    if student_requested:
        return True
    if subject and subject.lower() in SENSITIVE_SUBJECTS:
        return True
    if risk >= risk_threshold:
        return True
    if ai_confidence < confidence_threshold:
        return True
    return False


class ReviewItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    kind: ReviewKind
    payload: dict = Field(default_factory=dict)
    ai_confidence: float = 1.0
    risk: float = 0.0
    subject: Optional[str] = None
    status: ReviewStatus = ReviewStatus.PENDING
    final_payload: Optional[dict] = None
    decided_by: Optional[str] = None
    created_at: float = Field(default_factory=lambda: time.time())

    def resolved(self) -> dict:
        """The payload to deliver after a human decision (edited overrides)."""
        return self.final_payload if self.final_payload is not None else self.payload


class ReviewQueue:
    def __init__(self) -> None:
        self._items: Dict[str, ReviewItem] = {}

    def enqueue(self, item: ReviewItem) -> ReviewItem:
        self._items[item.id] = item
        return item

    def get(self, item_id: str) -> Optional[ReviewItem]:
        return self._items.get(item_id)

    def list(self, status: Optional[ReviewStatus] = None) -> List[ReviewItem]:
        items = list(self._items.values())
        if status is not None:
            items = [i for i in items if i.status is status]
        return items

    def pending(self) -> List[ReviewItem]:
        return self.list(ReviewStatus.PENDING)

    def decide(
        self,
        item_id: str,
        action: str,
        *,
        edited_payload: Optional[dict] = None,
        decided_by: str = "human",
    ) -> ReviewItem:
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(item_id)
        item.decided_by = decided_by
        if action == "approve":
            item.status = ReviewStatus.APPROVED
        elif action == "edit":
            item.status = ReviewStatus.EDITED
            item.final_payload = edited_payload or {}
        elif action == "reject":
            item.status = ReviewStatus.REJECTED
        elif action == "takeover":
            item.status = ReviewStatus.TAKEN_OVER
            if edited_payload is not None:
                item.final_payload = edited_payload
        else:
            raise ValueError(f"unknown action {action!r}")
        return item
