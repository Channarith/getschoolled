"""Assessment policy: adaptive presentation, pass gates, KSBs, and retention."""

import pytest

from aoep_shared.adaptive import Difficulty
from aoep_shared.assessment import QuizItem
from aoep_shared.assessment_policy import (
    AssessmentFormat,
    AssessmentStage,
    CheckpointPolicy,
    EvidenceDomain,
    decide_course_pass,
    evaluate_checkpoint,
    present_item,
    schedule_retention_checks,
    select_assessment_format,
)


def _items():
    return [
        QuizItem(
            item_id=f"item-{index}",
            topic="design",
            prompt=f"Question {index}",
            options=["wrong", "correct"],
            answer_index=1,
            difficulty=Difficulty.MEDIUM,
        )
        for index in range(3)
    ]


@pytest.mark.parametrize(
    ("profile_score", "expected"),
    [
        ("15115510", AssessmentFormat.VIDEO_AID),
        ("35115510", AssessmentFormat.AUDIO),
        ("55115510", AssessmentFormat.TEXT),
        ("75115510", AssessmentFormat.GAME),
    ],
)
def test_profile_score_selects_equivalent_assessment_shell(profile_score, expected):
    assert select_assessment_format(profile_score) == expected


def test_accessibility_and_drive_mode_override_presentation():
    assert select_assessment_format("35115510", needs_captions=True) == AssessmentFormat.TEXT
    assert select_assessment_format("75115510", device_mode="drive") == AssessmentFormat.AUDIO


def test_presented_items_never_expose_answer_key():
    for fmt in AssessmentFormat:
        if fmt == AssessmentFormat.AUTO:
            continue
        view = present_item(_items()[0], fmt)
        assert "answer_index" not in view
        assert view["item_id"] == "item-0"


def test_summative_policy_requires_score_ksb_coverage_and_domains():
    policy = CheckpointPolicy(
        checkpoint_id="final",
        stage=AssessmentStage.SUMMATIVE,
        pass_threshold=2 / 3,
        ksb_coverage_min=2 / 3,
        required_domains=[
            EvidenceDomain.KNOWLEDGE,
            EvidenceDomain.SKILL,
            EvidenceDomain.BEHAVIOUR,
        ],
    )
    items = _items()
    attempt = evaluate_checkpoint(
        student_id="s1",
        course_id="c1",
        policy=policy,
        items=items,
        chosen_indices=[1, 1, 1],
        presentation_format=AssessmentFormat.GAME,
        ksb_by_item={
            "item-0": ["K1"],
            "item-1": ["S1"],
            "item-2": ["B1"],
        },
        domain_by_item={
            "item-0": EvidenceDomain.KNOWLEDGE,
            "item-1": EvidenceDomain.SKILL,
            "item-2": EvidenceDomain.BEHAVIOUR,
        },
    )
    assert attempt.passed is True
    assert attempt.ksb_coverage == 1.0
    decision = decide_course_pass("s1", "c1", [attempt])
    assert decision.passed is True
    assert decision.ksb_codes_evidenced == ["B1", "K1", "S1"]


def test_formative_attempt_cannot_pass_course():
    attempt = evaluate_checkpoint(
        student_id="s1",
        course_id="c1",
        policy=CheckpointPolicy(checkpoint_id="mid", stage=AssessmentStage.FORMATIVE),
        items=_items(),
        chosen_indices=[1, 1, 1],
        presentation_format=AssessmentFormat.TEXT,
    )
    assert attempt.passed is True
    assert decide_course_pass("s1", "c1", [attempt]).passed is False


def test_retention_schedule_is_immediate_7_30_90_days():
    checks = schedule_retention_checks(
        student_id="s1",
        course_id="c1",
        completed_at=1_000.0,
        source_attempt_id="attempt-1",
    )
    assert [check.interval_days for check in checks] == [1, 7, 30, 90]
    assert checks[-1].due_at == 1_000.0 + 90 * 86_400
