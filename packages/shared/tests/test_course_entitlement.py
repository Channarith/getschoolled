"""One server-side answer to 'may this account take the full course?'"""

from aoep_shared.course_entitlement import (
    FREE, LOGIN_REQUIRED, MUST_PAY, PAID, entitled_to_course, is_free_member, unlocks_full_class,
)
from aoep_shared.purchases import PurchaseStore, _MemoryBackend

COURSE = "drivers-ed"


def _store(paid_for=None):
    store = PurchaseStore(_MemoryBackend())
    if paid_for:
        store.record_paid(account_id=paid_for, course_id=COURSE, amount_cents=1999, provider="stripe", provider_ref="cs_1")
    return store


def test_anonymous_is_login_required_and_never_unlocks():
    assert entitled_to_course(None, COURSE) == LOGIN_REQUIRED
    assert entitled_to_course({}, COURSE) == LOGIN_REQUIRED
    assert entitled_to_course({"is_admin": True}, COURSE) == LOGIN_REQUIRED  # a claim without an account id is nothing
    assert not unlocks_full_class(LOGIN_REQUIRED)


def test_admin_vip_and_premium_take_it_free():
    assert entitled_to_course({"id": "a", "is_admin": True}, COURSE) == FREE
    assert entitled_to_course({"id": "b", "membership_class": "vip", "tier": "premium"}, COURSE) == FREE
    assert entitled_to_course({"id": "c", "tier": "premium"}, COURSE) == FREE
    assert is_free_member({"id": "d", "membership_class": "VIP"})


def test_standard_members_pay_unless_the_owner_lists_their_tier(monkeypatch):
    for tier in ("free", "basic", "pro", ""):
        assert entitled_to_course({"id": "e", "tier": tier, "membership_class": "standard"}, COURSE) == MUST_PAY
    monkeypatch.setenv("COURSE_FREE_TIERS", "premium, pro")
    assert entitled_to_course({"id": "e", "tier": "pro"}, COURSE) == FREE


def test_a_purchase_on_record_unlocks_only_that_account_and_course():
    store = _store(paid_for="buyer")
    assert entitled_to_course({"id": "buyer", "tier": "free"}, COURSE, purchases=store) == PAID
    assert entitled_to_course({"id": "other", "tier": "free"}, COURSE, purchases=store) == MUST_PAY
    assert entitled_to_course({"id": "buyer", "tier": "free"}, "food-safety", purchases=store) == MUST_PAY


def test_a_refund_removes_the_entitlement():
    store = _store(paid_for="buyer")
    order = store.get_by_ref("stripe", "cs_1")
    store.mark_refunded(order["order_id"], reason="requested", by="admin")
    assert entitled_to_course({"id": "buyer", "tier": "free"}, COURSE, purchases=store) == MUST_PAY
