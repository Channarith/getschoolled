"""HIL core tests (Phase 10)."""

from aoep_shared.hil import (
    AutonomyLevel,
    ReviewItem,
    ReviewKind,
    ReviewQueue,
    ReviewStatus,
    should_escalate,
)


def test_human_led_always_escalates():
    assert should_escalate(autonomy=AutonomyLevel.HUMAN_LED) is True


def test_suggest_always_escalates():
    assert should_escalate(autonomy=AutonomyLevel.SUGGEST, risk=0.0, ai_confidence=1.0) is True


def test_autonomous_low_risk_does_not_escalate():
    assert should_escalate(autonomy=AutonomyLevel.AUTONOMOUS, risk=0.1, ai_confidence=0.9) is False


def test_autonomous_escalates_on_triggers():
    a = AutonomyLevel.AUTONOMOUS
    assert should_escalate(autonomy=a, risk=0.5) is True               # high risk
    assert should_escalate(autonomy=a, ai_confidence=0.2) is True       # low confidence
    assert should_escalate(autonomy=a, subject="medical") is True       # sensitive subject
    assert should_escalate(autonomy=a, student_requested=True) is True  # student asked for human


def test_queue_lifecycle_approve_edit_reject_takeover():
    q = ReviewQueue()
    item = q.enqueue(ReviewItem(kind=ReviewKind.ANSWER, payload={"text": "draft"}))
    assert q.pending()[0].id == item.id

    q.decide(item.id, "approve")
    assert q.get(item.id).status is ReviewStatus.APPROVED
    assert q.get(item.id).resolved() == {"text": "draft"}

    i2 = q.enqueue(ReviewItem(kind=ReviewKind.ANSWER, payload={"text": "draft2"}))
    q.decide(i2.id, "edit", edited_payload={"text": "human edit"})
    assert q.get(i2.id).status is ReviewStatus.EDITED
    assert q.get(i2.id).resolved() == {"text": "human edit"}

    i3 = q.enqueue(ReviewItem(kind=ReviewKind.GRADE, payload={"score": 1}))
    q.decide(i3.id, "reject")
    assert q.get(i3.id).status is ReviewStatus.REJECTED


def test_decide_unknown_raises():
    import pytest

    q = ReviewQueue()
    with pytest.raises(KeyError):
        q.decide("nope", "approve")
    item = q.enqueue(ReviewItem(kind=ReviewKind.ANSWER))
    with pytest.raises(ValueError):
        q.decide(item.id, "bogus")
