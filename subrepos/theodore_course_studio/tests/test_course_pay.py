"""A $19.99 card or PayPal payment unlocks the rest of the course."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from theodore_course_studio.course_pay import (
    CoursePayStore,
    payer_id,
    same_site_return,
    start_card_checkout,
    start_paypal_checkout,
)
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.types import CourseSlide, StudioCourse


class _Body:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> bool:
        return False


def test_payer_id_shares_the_audio_trial_account():
    assert payer_id("learner-a:audio") == "learner-a"


def test_return_url_must_stay_on_this_site():
    kept = same_site_return("http://testserver/studio?access=sample&paid=1", "testserver")
    assert kept == "http://testserver/studio?access=sample"
    try:
        same_site_return("https://evil.example/steal", "testserver")
    except ValueError as exc:
        assert "stay on this site" in str(exc)
    else:
        raise AssertionError("off-site return was accepted")


def test_card_checkout_asks_stripe_for_1999_cents(monkeypatch):
    monkeypatch.setenv("PAYMENT_API_KEY", "sk_test_example")
    seen = {}

    def opener(request, timeout=30):
        seen["url"] = request.full_url
        seen["body"] = request.data.decode()
        seen["auth"] = request.headers["Authorization"]
        return _Body({"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"})

    session = start_card_checkout(
        learner_id="learner-a",
        course_id="drivers-ed",
        title="Driver's Education",
        return_url="http://testserver/studio?access=sample",
        opener=opener,
    )
    assert session["url"].startswith("https://checkout.stripe.com/")
    assert "1999" in seen["body"]
    assert "card" in seen["body"]
    assert "{CHECKOUT_SESSION_ID}" in seen["body"]
    assert "card_number" not in seen["body"]
    assert seen["auth"] == "Bearer sk_test_example"


def test_paypal_checkout_asks_for_19_99(monkeypatch):
    monkeypatch.setenv("PAYPAL_API_KEY", "client")
    monkeypatch.setenv("PAYPAL_API_SECRET", "secret")
    calls = []

    def opener(request, timeout=30):
        calls.append(request.full_url)
        if request.full_url.endswith("/v1/oauth2/token"):
            return _Body({"access_token": "tok"})
        return _Body({
            "id": "ORDER1",
            "links": [{"rel": "approve", "href": "https://www.paypal.com/checkoutnow?token=ORDER1"}],
        })

    session = start_paypal_checkout(
        learner_id="learner-a",
        course_id="drivers-ed",
        title="Driver's Education",
        return_url="http://testserver/studio",
        opener=opener,
    )
    assert session["session_id"] == "ORDER1"
    assert "paypal.com" in session["url"]
    assert any(url.endswith("/v2/checkout/orders") for url in calls)


def test_checkout_without_keys_does_not_unlock(tmp_path, monkeypatch):
    import theodore_course_studio.main as main_mod

    for name in ("PAYMENT_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_API_KEY", "PAYPAL_API_KEY", "PAYPAL_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    old_store = main_mod._pay_store
    main_mod._pay_store = CoursePayStore(tmp_path / "payments.json")
    try:
        client = TestClient(main_mod.app)
        missing = client.post("/api/studio/pay/checkout", json={
            "course_id": "drivers-ed",
            "learner_id": "learner-a",
            "method": "card",
            "return_url": "http://testserver/studio",
        })
        assert missing.status_code == 503, missing.text
        assert "PAYMENT_API_KEY" in missing.text
    finally:
        main_mod._pay_store = old_store


def test_authorized_payment_opens_the_full_course(tmp_path, monkeypatch):
    import theodore_course_studio.main as main_mod

    old_builder = main_mod._builder
    old_teach_builder = main_mod._teach._builder
    old_store = main_mod._pay_store
    shared = CourseBuilder(data_dir=tmp_path / "data")
    main_mod._builder = shared
    main_mod._teach._builder = shared
    main_mod._pay_store = CoursePayStore(tmp_path / "payments.json")
    monkeypatch.setattr(main_mod, "card_is_paid", lambda session_id: session_id == "cs_paid")
    try:
        course = StudioCourse(
            course_id="paid-mini",
            title="Paid Mini",
            category="other",
            slides=[
                CourseSlide(index=0, title="One", body="First body of the class."),
                CourseSlide(index=1, title="Two", body="Second body of the class."),
            ],
        )
        shared.save_course(course)
        store = main_mod._pay_store
        store.remember(session_id="cs_paid", learner_id="learner-a:audio", course_id=course.course_id, method="card")
        client = TestClient(main_mod.app)
        confirmed = client.post("/api/studio/pay/confirm", json={"session_id": "cs_paid"})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["status"] == "paid"
        assert confirmed.json()["label"] == "$19.99"
        started = client.post("/api/studio/teach/start", json={
            "session_id": "paid-session",
            "course_id": course.course_id,
            "learner_id": "learner-a:audio",
            "access": "full",
            "use_voice_agent": False,
        })
        assert started.status_code == 200, started.text
        assert started.json()["access_mode"] == "full"
        assert started.json()["price"]["label"] == "$19.99"
    finally:
        main_mod._builder = old_builder
        main_mod._teach._builder = old_teach_builder
        main_mod._pay_store = old_store
