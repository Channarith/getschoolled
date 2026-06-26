"""Identity subscription activation and calendar billing."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="sub@example.com", password="S3cretpass"):
    return client.post("/auth/signup", json={"email": email, "password": password,
                                             "display_name": "Sub"}).json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_subscribe_standard_sets_billing_anchor():
    tok = _signup("std@example.com")["token"]
    out = client.post("/membership/subscribe", headers=_auth(tok), json={"tier": "basic"}).json()
    assert out["tier"] == "basic"
    assert out["membership_class"] == "standard"
    sub = out["subscription"]
    assert sub["price_usd"] == 19.99
    assert sub["display_name"] == "Standard"
    assert sub["billing_anchor_day"] is not None
    assert sub["next_billing_at"] is not None
    assert sub["ads"] is True


def test_subscribe_vip_is_ad_free_class():
    tok = _signup("vip@example.com")["token"]
    out = client.post("/membership/subscribe", headers=_auth(tok), json={"tier": "premium"}).json()
    assert out["tier"] == "premium"
    assert out["membership_class"] == "vip"
    assert out["subscription"]["price_usd"] == 29.99
    assert out["subscription"]["ads"] is False


def test_subscribe_free_clears_billing():
    tok = _signup("free@example.com")["token"]
    h = _auth(tok)
    client.post("/membership/subscribe", headers=h, json={"tier": "basic"})
    out = client.post("/membership/subscribe", headers=h, json={"tier": "free"}).json()
    assert out["tier"] == "free"
    assert out["subscription"]["next_billing_at"] is None


def test_me_includes_subscription():
    tok = _signup("me@example.com")["token"]
    h = _auth(tok)
    client.post("/membership/subscribe", headers=h, json={"tier": "premium"})
    me = client.get("/auth/me", headers=h).json()
    assert me["membership_class"] == "vip"
    assert me["subscription"]["price_usd"] == 29.99


def test_get_subscription_endpoint():
    tok = _signup("getsub@example.com")["token"]
    h = _auth(tok)
    client.post("/membership/subscribe", headers=h, json={"tier": "basic"})
    sub = client.get("/membership/subscription", headers=h).json()
    assert sub["billing_interval"] == "monthly"
    assert sub["price_usd"] == 19.99
