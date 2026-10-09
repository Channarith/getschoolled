"""Who may take a full Course Studio class from the public site.

The sales demo is a fixed 10-minute sample for a presentation. A learner takes
the rest of the class only when they have an account and that class is paid.
The authoring studio, which does not send an access mode, is unchanged.
"""

from __future__ import annotations

SAMPLE_MINUTES = 10
LIBRARY_COURSE_ID = "course-studio"
PAID_ENROLLMENT_STATUS = "paid"

# Public site courses. Driver's ed has a free 10-minute demo. Both full
# courses are paid unless the account is an admin.
PUBLIC_STUDIO_COURSES = (
    {
        "id": "drivers-ed",
        "title": "Driver's Education",
        "subtitle": "California permit prep",
        "category": "Driver education",
        "duration_min": SAMPLE_MINUTES,
        "preview": (
            "Anyone can take the 10-minute demo. "
            "The full course requires payment unless you are an admin."
        ),
        "deep_link": "/learn/drivers-ed",
        "demo_link": "/demo/drivers-ed",
        "tags": ["drivers-ed", "demo"],
    },
    {
        "id": "food-safety",
        "title": "Food Health & Safety",
        "subtitle": "California food handler prep",
        "category": "Food safety",
        "duration_min": 45,
        "preview": "Admins take this course. Everyone else pays.",
        "deep_link": "/learn/food-safety",
        "demo_link": "",
        "tags": ["food-safety"],
    },
)

SAMPLE_PREVIEW = (
    "This free trial is 10 minutes. "
    "Anyone can start it. Pay for the course when you want the full class."
)
SAMPLE_ENDED = (
    "Your free 10-minute trial has ended. "
    "Thanks for spending time with the lesson. "
    "Pay for the course when you want to keep going."
)


def full_class_allowed(
    *,
    registered: bool,
    enrollment_status: str = "",
    is_admin: bool = False,
) -> bool:
    """Admins take the full course. Everyone else needs a paid registration."""
    if is_admin:
        return True
    return bool(registered) and enrollment_status.strip().lower() == PAID_ENROLLMENT_STATUS


def resolve_teach_access(
    *,
    requested: str = "",
    registered: bool = False,
    enrollment_status: str = "",
    is_admin: bool = False,
) -> str:
    """Return ``sample`` or ``full``.

    ``sample`` is always the 10-minute demo, including for an admin or a paid
    account. ``full`` is honored for an admin, or for a registered learner who
    paid for that course. An empty request is the authoring studio.
    """
    mode = (requested or "").strip().lower()
    if mode == "sample":
        return "sample"
    if mode == "full":
        if full_class_allowed(
            registered=registered,
            enrollment_status=enrollment_status,
            is_admin=is_admin,
        ):
            return "full"
        return "sample"
    return "full"
