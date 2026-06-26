"""Content maturity gates with disability/accommodation override."""

from aoep_shared.content_access import may_access_course, needs_simplified_content


def test_adult_blocked_from_kids_content_by_default():
    allowed, reason = may_access_course(
        age_band="adult", maturity_rating="kids", needs_simplified=False,
    )
    assert allowed is False
    assert reason == "adult_on_kids_content_blocked"


def test_adult_allowed_kids_content_with_accessibility():
    allowed, reason = may_access_course(
        age_band="adult", maturity_rating="kids", needs_simplified=True,
    )
    assert allowed is True
    assert reason == "adult_accessibility_child_content"


def test_needs_simplified_from_accessibility_flags():
    assert needs_simplified_content(
        accessibility={"needs_extra_time": True},
    )


def test_needs_simplified_from_accommodations_notes():
    assert needs_simplified_content(
        accommodations_notes="I have dyslexia and need simpler lessons",
    )


def test_child_on_mature_content_blocked():
    allowed, _ = may_access_course(
        age_band="child", maturity_rating="mature", needs_simplified=False,
    )
    assert allowed is False
