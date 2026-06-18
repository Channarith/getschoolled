"""Outbound webhooks: sign/verify, delivery retries, dispatch (Phase 16)."""

from aoep_shared.webhooks import (
    MockSender,
    SubscriptionStore,
    WebhookEvent,
    WebhookSubscription,
    deliver,
    dispatch,
    sign_payload,
    verify_signature,
)


def test_sign_verify_roundtrip_and_tamper():
    body = b'{"a":1}'
    sig = sign_payload(body, "secret")
    assert verify_signature(body, sig, "secret") is True
    assert verify_signature(b'{"a":2}', sig, "secret") is False
    assert verify_signature(body, sig, "wrong") is False


def test_delivery_success_signs_payload():
    sub = WebhookSubscription(url="https://x.test/hook", secret="s")
    sender = MockSender()
    res = deliver(sub, WebhookEvent(event_type="enrollment.paid", data={"id": 1}), sender=sender)
    assert res.delivered is True and res.attempts == 1
    sent = sender.calls[0]
    assert sent["headers"]["X-AOEP-Event"] == "enrollment.paid"
    assert verify_signature(sent["body"], sent["headers"]["X-AOEP-Signature"], "s")


def test_delivery_retries_then_succeeds():
    sub = WebhookSubscription(url="https://x.test/hook", secret="s")
    sender = MockSender(fail_times=2)
    res = deliver(sub, WebhookEvent(event_type="e"), sender=sender, max_attempts=3)
    assert res.delivered is True and res.attempts == 3


def test_delivery_gives_up():
    sub = WebhookSubscription(url="https://x.test/hook", secret="s")
    sender = MockSender(fail_times=5)
    res = deliver(sub, WebhookEvent(event_type="e"), sender=sender, max_attempts=3)
    assert res.delivered is False and res.attempts == 3


def test_dispatch_only_matching_event_types():
    store = SubscriptionStore()
    store.add(WebhookSubscription(url="https://a.test", event_types=["paid"], secret="s"))
    store.add(WebhookSubscription(url="https://b.test", event_types=["refund"], secret="s"))
    store.add(WebhookSubscription(url="https://c.test", event_types=[], secret="s"))  # all
    sender = MockSender()
    results = dispatch(store, WebhookEvent(event_type="paid"), sender=sender)
    assert len(results) == 2  # the "paid" sub + the catch-all
