"""Receipts and credit notes: itemized, one per order, last four digits only, checkable, and honest about unset seller details."""

import io

from aoep_shared import receipts

ORDER = {
    "order_id": "SAL-2026-000007", "account_id": "acct-1", "email": "buyer@example.com", "course_id": "drivers-ed",
    "amount_cents": 1999, "tax_cents": 145, "total_cents": 2144, "currency": "usd", "provider": "stripe", "last4": "4242",
    "status": "paid", "created_at": 1_800_000_000.0,
}


def test_the_receipt_states_every_required_fact():
    r = receipts.build_receipt(ORDER)
    assert r["order_id"] == "SAL-2026-000007" and r["buyer_email"] == "buyer@example.com"
    assert "UTC" in r["date_utc"] and "America/Los_Angeles" in r["date_local"]
    assert [l["amount"] for l in r["lines"]] == ["$19.99", "$1.45"] and r["total"] == "$21.44"
    assert r["payment_method"] == "Card ending 4242"
    assert r["refund_policy_url"].endswith("/refund-policy") and "AI-assisted instruction" in r["disclaimer"]
    assert "not a DMV-approved" in r["disclaimer"]


def test_no_tax_line_when_no_tax_was_collected():
    r = receipts.build_receipt({**ORDER, "tax_cents": 0, "total_cents": 1999})
    assert len(r["lines"]) == 1 and r["total"] == "$19.99"


def test_a_full_card_number_can_never_appear():
    r = receipts.build_receipt({**ORDER, "last4": "4242424242424242"})
    assert r["payment_method"] == "Card ending 4242" and "4242424242424242" not in receipts.render_html(r)


def test_unset_seller_details_are_visibly_unset_not_invented():
    page = receipts.render_html(receipts.build_receipt(ORDER))
    assert page.count("[to be set by the seller]") >= 3 and "DRAFT wording" in page


def test_seller_details_come_from_configuration(monkeypatch):
    monkeypatch.setenv("SELLER_LEGAL_NAME", "Salareen Learning LLC")
    monkeypatch.setenv("SELLER_SUPPORT_EMAIL", "help@example.com")
    page = receipts.render_html(receipts.build_receipt(ORDER))
    assert "Salareen Learning LLC" in page and "help@example.com" in page


def test_html_is_escaped():
    page = receipts.render_html(receipts.build_receipt({**ORDER, "email": '"><script>alert(1)</script>'}))
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_the_same_order_always_renders_the_same_receipt_and_the_code_checks_out():
    a, b = receipts.build_receipt(ORDER), receipts.build_receipt(dict(ORDER))
    assert a == b and a["code"] == receipts.verification_code(ORDER)
    assert receipts.verification_code({**ORDER, "total_cents": 1}) != a["code"]  # a tampered total no longer matches


def test_store_purchases_say_the_store_sends_its_own_receipt():
    r = receipts.build_receipt({**ORDER, "provider": "apple", "last4": "", "tax_cents": 0, "total_cents": 1999})
    assert r["payment_method"] == "Apple App Store" and "App Store or Google Play sends its own receipt" in r["store_note"]


def test_a_refunded_order_gets_a_credit_note():
    refunded = {**ORDER, "status": "refunded", "refunded": {"reason": "customer_request", "by": "acct-1", "at": 1_800_100_000.0, "amount_cents": 2144}}
    note = receipts.build_receipt(refunded, "credit_note")
    assert note["kind"] == "credit_note" and note["refund_amount"] == "$21.44" and note["code"] != receipts.build_receipt(refunded)["code"]
    assert "Credit note" in receipts.render_html(note) and "Refunded:" in receipts.render_html(note)


def test_pdf_is_produced_when_reportlab_is_present():
    pdf = receipts.render_pdf(receipts.build_receipt(ORDER))
    assert pdf is None or pdf.startswith(b"%PDF")


class _FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout=0):
        self.args = (host, port)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self): pass
    def login(self, user, password): pass
    def send_message(self, msg): _FakeSMTP.sent.append(msg)


def test_email_is_never_a_silent_success(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    r = receipts.build_receipt(ORDER)
    assert receipts.send_receipt_email(r, "buyer@example.com")["sent"] is False
    assert receipts.send_receipt_email(r, "")["sent"] is False


def test_email_goes_out_through_smtp_when_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SELLER_SUPPORT_EMAIL", "help@example.com")
    _FakeSMTP.sent = []
    result = receipts.send_receipt_email(receipts.build_receipt(ORDER), "buyer@example.com", smtp_factory=_FakeSMTP)
    assert result["sent"] is True and _FakeSMTP.sent[0]["To"] == "buyer@example.com" and _FakeSMTP.sent[0]["From"] == "help@example.com"
    assert "SAL-2026-000007" in _FakeSMTP.sent[0]["Subject"]
