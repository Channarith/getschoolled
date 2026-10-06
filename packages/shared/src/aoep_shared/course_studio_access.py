"""Who may take a full Course Studio class from the public site.

The sales demo is a fixed 10-minute sample for a presentation. A learner takes
the rest of the class only when they have an account and that class is paid.
The authoring studio, which does not send an access mode, is unchanged.
"""

from __future__ import annotations

SAMPLE_MINUTES = 10
LIBRARY_COURSE_ID = "course-studio"
PAID_ENROLLMENT_STATUS = "paid"

SAMPLE_PREVIEW = (
    "10-minute sample for this presentation. "
    "A registered learner who has paid for the class takes the full course."
)
SAMPLE_ENDED = (
    "This 10-minute sample has ended. "
    "Register and pay for the class to take the full course."
)


def full_class_allowed(*, registered: bool, enrollment_status: str = "") -> bool:
    """Full class requires both a registered account and a paid enrollment."""
    return bool(registered) and enrollment_status.strip().lower() == PAID_ENROLLMENT_STATUS


def resolve_teach_access(
    *,
    requested: str = "",
    registered: bool = False,
    enrollment_status: str = "",
) -> str:
    """Return ``sample`` or ``full``.

    ``sample`` is always a sample, including when the presenter is paid.
    ``full`` is honored only for a registered learner who paid for the class.
    An empty request is the authoring studio and stays a full session.
    """
    mode = (requested or "").strip().lower()
    if mode == "sample":
        return "sample"
    if mode == "full":
        if full_class_allowed(registered=registered, enrollment_status=enrollment_status):
            return "full"
        return "sample"
    return "full"
