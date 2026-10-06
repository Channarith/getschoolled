"""Sales-demo sample versus a paid, registered full class."""

from aoep_shared.course_studio_access import (
    SAMPLE_MINUTES,
    full_class_allowed,
    resolve_teach_access,
)


def test_full_class_requires_registration_and_payment():
    assert full_class_allowed(registered=True, enrollment_status="paid") is True
    assert full_class_allowed(registered=True, enrollment_status="Paid") is True
    assert full_class_allowed(registered=True, enrollment_status="enrolled") is False
    assert full_class_allowed(registered=False, enrollment_status="paid") is False
    assert full_class_allowed(registered=True, enrollment_status="") is False


def test_sales_demo_stays_a_sample_even_for_a_paid_account():
    assert resolve_teach_access(
        requested="sample", registered=True, enrollment_status="paid"
    ) == "sample"


def test_unpaid_full_request_is_downgraded():
    assert resolve_teach_access(
        requested="full", registered=True, enrollment_status="enrolled"
    ) == "sample"
    assert resolve_teach_access(
        requested="full", registered=False, enrollment_status="paid"
    ) == "sample"


def test_paid_registered_request_is_the_full_class():
    assert resolve_teach_access(
        requested="full", registered=True, enrollment_status="paid"
    ) == "full"


def test_authoring_studio_without_a_mode_stays_full():
    assert resolve_teach_access() == "full"
    assert SAMPLE_MINUTES == 10
