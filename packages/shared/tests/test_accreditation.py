"""Unit tests for accreditation / certification account hard rule."""

from aoep_shared.accreditation import (
    ACCREDITATION_ACCOUNT_REQUIRED,
    ACCREDITATION_VERIFIED_PASS_REQUIRED,
    certification_meta,
    is_certifiable_lesson,
    may_mark_accreditation_passed,
    may_start_for_accreditation,
    requires_registered_account,
)


def test_sample_lessons_do_not_require_account():
    for lid in ("intro-python", "intro-to-photosynthesis", "arithmetic", "intro-science"):
        assert is_certifiable_lesson(lid) is False
        assert requires_registered_account(lid) is False
        ok, reason = may_start_for_accreditation(lid, account_id=None)
        assert ok is True
        assert reason == "sample_or_non_certifiable"


def test_certifiable_lessons_require_registered_account():
    for lid in (
        "osha-general-safety",
        "cpr-first-aid-certification",
        "hipaa-privacy-security",
        "comptia-a-plus",
    ):
        assert is_certifiable_lesson(lid) is True
        assert requires_registered_account(lid) is True
        ok, reason = may_start_for_accreditation(lid, account_id=None)
        assert ok is False
        assert reason == ACCREDITATION_ACCOUNT_REQUIRED


def test_registered_free_account_allowed_for_accreditation():
    """Paid membership is NOT required — only a registered account."""
    ok, reason = may_start_for_accreditation(
        "osha-general-safety", account_id="free-user-acct",
    )
    assert ok is True
    assert reason == "registered_account"


def test_certification_meta():
    body, ceu = certification_meta("osha-general-safety")
    assert body == "OSHA"
    assert ceu == 2.0
    body2, ceu2 = certification_meta("intro-python")
    assert body2 == ""
    assert ceu2 == 0.0


def test_mark_passed_gate():
    ok, reason = may_mark_accreditation_passed(
        "osha-general-safety", has_verified_pass_token=False,
    )
    assert ok is False
    assert reason == ACCREDITATION_VERIFIED_PASS_REQUIRED
    ok2, _ = may_mark_accreditation_passed(
        "osha-general-safety", has_verified_pass_token=True,
    )
    assert ok2 is True
    ok3, reason3 = may_mark_accreditation_passed(
        "intro-python", has_verified_pass_token=False,
    )
    assert ok3 is True
    assert reason3 == "non_certifiable"
