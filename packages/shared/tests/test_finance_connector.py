"""Finance connector: payment-event parsing + mock connector (Phase 17)."""

from aoep_shared.connectors.finance import MockFinanceConnector, parse_payment_event


def test_parse_grant_event():
    payload = {"type": "checkout.session.completed",
               "data": {"object": {"customer": "cus_1", "amount_total": 4999,
                                    "currency": "usd", "metadata": {"entitlement": "pro"}}}}
    ev = parse_payment_event("stripe", payload)
    assert ev.kind == "grant"
    assert ev.customer == "cus_1"
    assert abs(ev.amount - 49.99) < 1e-6
    assert ev.entitlement == "pro"


def test_parse_revoke_event():
    payload = {"type": "charge.refunded", "data": {"object": {"customer": "cus_1"}}}
    assert parse_payment_event("stripe", payload).kind == "revoke"


def test_parse_unknown_is_ignore():
    assert parse_payment_event("stripe", {"type": "ping"}).kind == "ignore"


def test_mock_finance_records():
    fc = MockFinanceConnector()
    fc.record_revenue(49.99, memo="x")
    fc.payout("acct_1", 20.0)
    assert fc.revenue[0]["amount"] == 49.99
    assert fc.payouts[0]["account"] == "acct_1"
