"""Accreditation / certification access rules.

HARD RULE
---------
Guests and unregistered visitors may take **sample** (non-certifiable) courses
for exploration and learning. They must **not** start or complete courses that
award accreditation, certification, CEUs, or a verified professional pass
unless they have a registered account.

Registered free-tier accounts are allowed — the gate is account registration,
not paid membership. Membership entitlements (solo/VIP/etc.) remain a separate
layer in ``aoep_shared.entitlements``.

Source of truth for which lessons are certifiable: ``CERTIFIABLE_LESSONS`` in
``aoep_shared.learnable.index``.
"""

from __future__ import annotations

from typing import Optional, Tuple

# Stable machine-readable / human-readable rejection for HTTP APIs.
ACCREDITATION_ACCOUNT_REQUIRED = "accreditation_account_required"
ACCREDITATION_ACCOUNT_REQUIRED_DETAIL = (
    "Accreditation and certification courses require a registered account. "
    "Guests may take sample courses only — sign up or sign in to continue "
    "this course for credit."
)
ACCREDITATION_VERIFIED_PASS_REQUIRED = "accreditation_verified_pass_required"
ACCREDITATION_VERIFIED_PASS_DETAIL = (
    "Marking an accreditation/certification course as PASSED requires a "
    "verified summative pass decision from a registered account. Guests "
    "cannot receive accreditation credit."
)


def is_certifiable_lesson(lesson_id: str) -> bool:
    """True when ``lesson_id`` can award certification / CEU / professional credit."""
    if not lesson_id:
        return False
    from aoep_shared.learnable.index import CERTIFIABLE_LESSONS

    return lesson_id in CERTIFIABLE_LESSONS


def certification_meta(lesson_id: str) -> Tuple[str, float]:
    """Return ``(certification_body, ceu_credits)`` or ``("", 0.0)`` if not certifiable."""
    if not lesson_id:
        return "", 0.0
    from aoep_shared.learnable.index import CERTIFIABLE_LESSONS

    return CERTIFIABLE_LESSONS.get(lesson_id, ("", 0.0))


def requires_registered_account(lesson_id: str) -> bool:
    """HARD RULE: certifiable courses require a registered account."""
    return is_certifiable_lesson(lesson_id)


def may_start_for_accreditation(
    lesson_id: str,
    *,
    account_id: Optional[str],
) -> Tuple[bool, str]:
    """Decide whether a caller may start a lesson that awards accreditation.

    Returns ``(allowed, reason_code)``. Non-certifiable (sample) lessons always
    allow start regardless of auth — guests may explore samples. Certifiable
    lessons require a non-empty ``account_id`` from a verified auth token.
    """
    if not requires_registered_account(lesson_id):
        return True, "sample_or_non_certifiable"
    if account_id and str(account_id).strip():
        return True, "registered_account"
    return False, ACCREDITATION_ACCOUNT_REQUIRED


def may_mark_accreditation_passed(
    course_id: str,
    *,
    has_verified_pass_token: bool,
) -> Tuple[bool, str]:
    """Decide whether PASSED may be recorded for an accreditation course.

    Certifiable courses always require a verified summative pass token — even
    in local/dev — so guests and unverified clients cannot self-award credit.
    Non-certifiable courses defer to the caller's existing unverified-pass policy.
    """
    if not is_certifiable_lesson(course_id):
        return True, "non_certifiable"
    if has_verified_pass_token:
        return True, "verified_pass_token"
    return False, ACCREDITATION_VERIFIED_PASS_REQUIRED
