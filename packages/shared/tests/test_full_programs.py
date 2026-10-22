"""Full programs are hundreds of slides. Lessons stay short. Cards are not issued."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

from aoep_shared.accreditation import (
    ACCREDITATION_ACCOUNT_REQUIRED,
    ACCREDITATION_VERIFIED_PASS_REQUIRED,
)
from aoep_shared.full_programs import (
    MIN_FULL_PROGRAM_SLIDES,
    HAND_BUILT_PROGRAMS,
    accreditation_view,
    discover_programs,
    expand_programs,
    may_award_program_completion,
    may_issue_external_card,
    plan_program,
    published_slide_counts,
)
from aoep_shared.harvest.generate import MAX_SLIDES_PER_LESSON


def _by_domain(domain: str):
    return next(spec for spec in HAND_BUILT_PROGRAMS if spec.domain == domain)


def test_program_floor_is_hundreds_and_lesson_cap_stays_short():
    assert MIN_FULL_PROGRAM_SLIDES >= 200
    assert MAX_SLIDES_PER_LESSON <= 20


def test_named_programs_plan_hundreds_of_unique_slides():
    domains = {"ai", "cpr", "automotive", "grade-school", "vocabulary"}
    assert {spec.domain for spec in HAND_BUILT_PROGRAMS} == domains
    for spec in HAND_BUILT_PROGRAMS:
        plan = plan_program(spec)
        assert plan.slide_count >= MIN_FULL_PROGRAM_SLIDES
        assert plan.has_summative
        texts = [item.text for item in spec.resolved_objectives()]
        assert len(texts) == len(set(texts))


def test_built_program_is_partitioned_into_short_lessons():
    from aoep_shared.full_programs import build_program_course

    _plan, lessons = build_program_course(_by_domain("vocabulary"))
    assert sum(len(lesson.slides) for lesson in lessons) >= MIN_FULL_PROGRAM_SLIDES
    assert all(len(lesson.slides) <= MAX_SLIDES_PER_LESSON for lesson in lessons)
    assert len(lessons) > 1
    assert lessons[0].lesson_count == len(lessons)


def test_short_published_seeds_are_not_completable():
    counts = published_slide_counts()
    cpr = _by_domain("cpr")
    published = sum(counts.get(lesson_id, 0) for lesson_id in cpr.seed_lesson_ids)
    assert published < MIN_FULL_PROGRAM_SLIDES
    ok, reason = may_award_program_completion(
        cpr,
        published_slides=published,
        account_id="acct-1",
        has_verified_pass_token=True,
        human_reviewed=True,
    )
    assert ok is False
    assert reason == "below_program_slide_floor"


def test_reviewed_full_program_awards_salareen_record_not_an_outside_card():
    cpr = replace(_by_domain("cpr"), human_reviewed=True, needs_expansion=False)
    ok, reason = may_award_program_completion(
        cpr,
        published_slides=MIN_FULL_PROGRAM_SLIDES,
        account_id="acct-1",
        has_verified_pass_token=True,
    )
    assert ok is True
    assert reason == "salareen_program_completion"

    ok, reason = may_award_program_completion(
        cpr,
        published_slides=MIN_FULL_PROGRAM_SLIDES,
        account_id="acct-1",
        has_verified_pass_token=True,
        request_external_card=True,
    )
    assert ok is False
    assert reason == "external_card_not_issued"

    ok, reason = may_award_program_completion(
        cpr,
        published_slides=MIN_FULL_PROGRAM_SLIDES,
        account_id=None,
        has_verified_pass_token=True,
    )
    assert reason == ACCREDITATION_ACCOUNT_REQUIRED

    ok, reason = may_award_program_completion(
        cpr,
        published_slides=MIN_FULL_PROGRAM_SLIDES,
        account_id="acct-1",
        has_verified_pass_token=False,
    )
    assert reason == ACCREDITATION_VERIFIED_PASS_REQUIRED


def test_unsigned_draft_stays_blocked_even_at_the_slide_floor():
    ai = _by_domain("ai")
    ok, reason = may_award_program_completion(
        ai,
        published_slides=MIN_FULL_PROGRAM_SLIDES,
        account_id="acct-1",
        has_verified_pass_token=True,
        human_reviewed=False,
    )
    assert ok is False
    assert reason == "awaiting_human_review"


def test_every_sample_lesson_belongs_to_one_program():
    programs = discover_programs()
    seen: dict[str, str] = {}
    for spec in programs:
        for lesson_id in spec.seed_lesson_ids:
            assert lesson_id not in seen, lesson_id
            seen[lesson_id] = spec.program_id
    for lesson_id in published_slide_counts():
        assert lesson_id in seen
    for spec in programs:
        if spec.needs_expansion:
            assert plan_program(spec).slide_count >= MIN_FULL_PROGRAM_SLIDES
        else:
            published = sum(
                published_slide_counts().get(lesson_id, 0)
                for lesson_id in spec.seed_lesson_ids
            )
            assert published >= MIN_FULL_PROGRAM_SLIDES


def test_cpr_status_names_the_body_and_refuses_the_card():
    view = accreditation_view("cpr-first-aid-certification")
    assert view["program_id"] == "cpr-first-aid"
    assert view["external_body"] == "AHA"
    assert view["external_card_issued"] is False
    assert view["published_slide_count"] < MIN_FULL_PROGRAM_SLIDES
    assert view["planned_slide_count"] >= MIN_FULL_PROGRAM_SLIDES
    assert view["completion_block"] == "below_program_slide_floor"
    assert view["program_completion_eligible"] is False
    assert "not an aha" in view["completion_scope"].lower()


def test_grade_school_record_is_not_a_diploma():
    view = accreditation_view("arithmetic")
    assert view["domain"] == "grade-school"
    assert "diploma" in view["completion_scope"].lower()
    assert view["external_card_issued"] is False


def test_async_plan_writes_a_manifest(tmp_path: Path):
    spec = _by_domain("vocabulary")
    manifests = asyncio.run(
        expand_programs([spec], tmp_path, plan_only=True, concurrency=2)
    )
    assert manifests[0]["slide_count"] >= MIN_FULL_PROGRAM_SLIDES
    payload = json.loads((tmp_path / spec.program_id / "program.json").read_text())
    assert payload["external_card_issued"] is False
    assert payload["status"] == "review_draft"


def test_external_card_stays_off_until_a_person_signs_and_subjects_clear():
    refused, reason = may_issue_external_card(human_signed=False, subject_min=0.9)
    assert refused is False
    assert reason == "human_signature_required"
    refused, reason = may_issue_external_card(human_signed=True, subject_min=0.14)
    assert refused is False
    assert reason == "subject_floor"
    refused, reason = may_issue_external_card(human_signed=True, subject_min=0.9)
    assert refused is False
    assert reason == "external_card_not_issued"
    view = accreditation_view("cpr-first-aid-certification")
    assert view["external_card_issued"] is False
    assert view["external_card_block"] == "human_signature_required"
