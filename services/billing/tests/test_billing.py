from fastapi.testclient import TestClient

from billing.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["service"] == "billing"


def test_plans_listed():
    plans = client.get("/plans").json()
    assert set(plans) == {"free", "basic", "pro", "premium"}


def test_can_start_free_blocks_solo():
    body = client.post(
        "/entitlements/can-start",
        json={"tier": "free", "class_type": "solo", "language": "en"},
    ).json()
    assert body["allowed"] is False
    assert body["reasons"]


def test_can_start_pro_allows_solo_all_langs():
    body = client.post(
        "/entitlements/can-start",
        json={"tier": "pro", "class_type": "solo", "language": "sw"},
    ).json()
    assert body["allowed"] is True


def test_checkout_local_uses_sandbox():
    body = client.post(
        "/checkout", json={"customer_id": "cust_1", "plan": "pro"}
    ).json()
    assert body["provider"] == "sandbox"
    assert body["session_id"].startswith("cs_sandbox_")
