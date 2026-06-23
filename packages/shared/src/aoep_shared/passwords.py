"""Password policy (shared, stdlib-only).

Single source of truth for account password strength so signup, password
change, and any future flow enforce the SAME rules. The web mirrors these for
inline validation. Policy: at least 8 characters, with at least one letter and
one number, and not a single repeated character.
"""

from __future__ import annotations

from typing import List

MIN_PASSWORD_LENGTH = 8

# A tiny blocklist of obviously-weak passwords that still pass the structural
# checks; extend as needed. Compared case-insensitively.
_COMMON_WEAK = {
    "password", "password1", "passw0rd", "12345678", "123456789", "1234567890",
    "qwerty12", "qwertyui", "abc12345", "letmein1", "iloveyou", "admin123",
}


def password_problems(password: str) -> List[str]:
    """Return a list of unmet requirements (empty list == acceptable)."""
    pw = password or ""
    problems: List[str] = []
    if len(pw) < MIN_PASSWORD_LENGTH:
        problems.append(f"at least {MIN_PASSWORD_LENGTH} characters")
    if not any(c.isalpha() for c in pw):
        problems.append("at least one letter")
    if not any(c.isdigit() for c in pw):
        problems.append("at least one number")
    if pw and len(set(pw)) == 1:
        problems.append("more than one distinct character")
    if pw.lower() in _COMMON_WEAK:
        problems.append("a less common password (this one is too easy to guess)")
    return problems


def is_strong_password(password: str) -> bool:
    return not password_problems(password)


def validate_password(password: str) -> None:
    """Raise ValueError with a human-readable message if the password is weak."""
    problems = password_problems(password)
    if problems:
        raise ValueError("Password must have " + ", ".join(problems) + ".")
