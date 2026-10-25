"""Recording a payment twice (return page plus webhook, or a webhook retry) grants the course once."""

from aoep_shared.purchases import PurchaseStore, _MemoryBackend


def test_return_page_and_webhook_for_the_same_session_record_one_order():
    store = PurchaseStore(_MemoryBackend())
    args = dict(account_id="acct-1", course_id="drivers-ed", amount_cents=1999, provider="stripe", provider_ref="cs_1")
    first, created = store.record_paid(**args)
    second, created_again = store.record_paid(**args)
    assert created and not created_again and first["order_id"] == second["order_id"]
    assert len(store.list_for_account("acct-1")) == 1
