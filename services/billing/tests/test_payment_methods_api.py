"""API tests for payment-method listing and method-aware checkout (local mode)."""

from fastapi.testclient import TestClient

from billing.main import app

client = TestClient(app)


def test_payment_methods_listed_and_available_in_sandbox():
    body = client.get("/payment-methods").json()
    by_method = {m["method"]: m for m in body["methods"]}
    # All requested methods are present...
    for name in ("apple_pay", "google_pay", "venmo", "zelle", "cashapp", "paypal", "card"):
        assert name in by_method, f"missing {name}"
    # ...and the local sandbox can process them all.
    assert all(m["available"] for m in body["methods"])
    assert by_method["venmo"]["processor"] == "paypal"
    assert by_method["apple_pay"]["processor"] == "stripe"
    assert by_method["zelle"]["processor"] == "manual"


def test_checkout_with_apple_pay():
    body = client.post(
        "/checkout",
        json={"customer_id": "c1", "plan": "pro", "method": "apple_pay"},
    ).json()
    assert body["method"] == "apple_pay"
    assert body["provider"] == "sandbox"
    assert "apple_pay" in body["url"]


def test_checkout_with_venmo_and_cashapp():
    for method in ("venmo", "cashapp", "google_pay"):
        body = client.post(
            "/checkout",
            json={"customer_id": "c1", "plan": "basic", "method": method},
        ).json()
        assert body["method"] == method


def test_checkout_zelle_returns_manual_instructions():
    body = client.post(
        "/checkout",
        json={"customer_id": "c1", "plan": "pro", "method": "zelle"},
    ).json()
    assert body["method"] == "zelle"
    assert body["url"] == ""
    assert body["instructions"]


def test_checkout_rejects_unknown_method():
    r = client.post(
        "/checkout",
        json={"customer_id": "c1", "plan": "pro", "method": "bitcoin"},
    )
    assert r.status_code == 422  # not a valid PaymentMethod enum value
