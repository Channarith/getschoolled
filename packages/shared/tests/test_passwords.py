"""Password policy: >= 8 chars, a letter + a number, not trivial."""

from __future__ import annotations

import pytest

from aoep_shared.passwords import (
    MIN_PASSWORD_LENGTH,
    is_strong_password,
    password_problems,
    validate_password,
)


def test_min_length_is_eight():
    assert MIN_PASSWORD_LENGTH == 8


@pytest.mark.parametrize("pw", ["S3cretpass", "newpass12", "x12345678", "Tr0ub4dour"])
def test_accepts_strong_passwords(pw):
    assert is_strong_password(pw)
    assert password_problems(pw) == []
    validate_password(pw)  # does not raise


@pytest.mark.parametrize("pw,needle", [
    ("short1", "at least 8 characters"),       # too short
    ("abcdefgh", "at least one number"),         # letters only
    ("12345678", "a less common password"),      # common AND digits-only -> flagged
    ("00000000", "more than one distinct character"),  # all same
    ("", "at least 8 characters"),
    ("password", "at least one number"),
])
def test_rejects_weak_passwords(pw, needle):
    probs = password_problems(pw)
    assert probs, f"expected {pw!r} to be rejected"
    assert any(needle in p for p in probs), f"{pw!r} -> {probs}"
    assert not is_strong_password(pw)
    with pytest.raises(ValueError):
        validate_password(pw)


def test_digits_only_long_needs_a_letter():
    # 8+ digits but no letter -> rejected (so "88888888" is not a valid user pw).
    assert "at least one letter" in password_problems("87654321")
