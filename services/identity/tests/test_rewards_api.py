"""Identity rewards: earn on pass, view, redeem (Netflix-style incentives)."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _new_user(email):
    return client.post("/auth/signup", json={"email": email, "password": "S3cretpass"}).json()["token"]


def test_points_awarded_on_pass_and_idempotent():
    h = _auth(_new_user("rw1@example.com"))
    client.post("/enrollments", headers=h, json={"course_id": "c1", "title": "Adv Bio"})
    # Pass an advanced, hands-on course with a high score.
    out = client.post("/enrollments/c1/status", headers=h,
                      json={"status": "passed", "score": 1.0, "level": "advanced", "hands_on": True}).json()
    bal = out["points_balance"]
    assert bal > 0  # advanced(300) + score bonus + hands-on(50)

    # Re-passing must NOT double-award.
    again = client.post("/enrollments/c1/status", headers=h, json={"status": "passed"}).json()
    assert again["points_balance"] == bal


def test_ai_agent_reward_grant(monkeypatch):
    """The AI agent mints a signed voucher; identity verifies it and credits the
    learner. Forged vouchers are rejected; replays don't double-credit."""
    from aoep_shared.auth import sign_token

    key = "shared-internal-key"
    monkeypatch.setenv("INTERNAL_TOKEN_KEY", key)
    h = _auth(_new_user("grant1@example.com"))

    voucher = sign_token(
        {"scope": "reward", "points": 15, "reason": "Great question!",
         "ref": "sess1", "nonce": "n-abc"}, key.encode("utf-8"), ttl_s=3600)
    out = client.post("/rewards/grant", headers=h, json={"grant": voucher}).json()
    assert out["earned"] == 15 and out["balance"] >= 15

    # Replaying the same voucher is idempotent (nonce already used).
    again = client.post("/rewards/grant", headers=h, json={"grant": voucher}).json()
    assert again["earned"] == 0 and again["balance"] == out["balance"]

    # A voucher signed with the WRONG key is rejected.
    forged = sign_token({"scope": "reward", "points": 999, "nonce": "n-x"},
                        b"attacker-key", ttl_s=3600)
    assert client.post("/rewards/grant", headers=h, json={"grant": forged}).status_code == 403

    # Wrong scope is rejected.
    wrong = sign_token({"scope": "internal", "points": 10, "nonce": "n-y"},
                       key.encode("utf-8"), ttl_s=3600)
    assert client.post("/rewards/grant", headers=h, json={"grant": wrong}).status_code == 403

    # Over-cap amount is rejected.
    big = sign_token({"scope": "reward", "points": 9999, "nonce": "n-z"},
                     key.encode("utf-8"), ttl_s=3600)
    assert client.post("/rewards/grant", headers=h, json={"grant": big}).status_code == 400


def test_reward_grant_not_configured(monkeypatch):
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)
    h = _auth(_new_user("grant2@example.com"))
    r = client.post("/rewards/grant", headers=h, json={"grant": "x.y"})
    assert r.status_code == 503


def test_rewards_summary_and_catalog():
    h = _auth(_new_user("rw2@example.com"))
    client.post("/enrollments", headers=h, json={"course_id": "c2", "title": "X"})
    client.post("/enrollments/c2/status", headers=h, json={"status": "passed", "level": "advanced"})

    summary = client.get("/rewards", headers=h).json()
    assert summary["balance"] >= 300
    assert any(e["reason"] == "course_passed" for e in summary["ledger"])

    catalog = client.get("/rewards/catalog").json()
    ids = {p["id"] for p in catalog["prizes"]}
    assert {"discount_10", "raffle_ps5", "raffle_gold"} <= ids
    # Revamped catalog: swag/attire, gift cards, and a richer raffle set.
    assert {"swag_tshirt", "gift_amazon_5", "gift_visa_10"} <= ids
    gift = next(p for p in catalog["prizes"] if p["id"] == "gift_amazon_5")
    assert gift["kind"] == "gift_card" and gift["kind_label"] == "Gift card"
    assert gift["detail"]["value_usd"] == 5


def test_redeem_discount_and_raffle():
    h = _auth(_new_user("rw3@example.com"))
    # Earn enough points: pass several advanced courses (raffle entries cost
    # more now, so fund the account accordingly).
    for i in range(6):
        cid = f"c{i}"
        client.post("/enrollments", headers=h, json={"course_id": cid, "title": cid})
        client.post(f"/enrollments/{cid}/status", headers=h,
                    json={"status": "passed", "level": "advanced", "score": 1.0})
    bal0 = client.get("/rewards", headers=h).json()["balance"]

    disc = client.post("/rewards/redeem", headers=h, json={"prize_id": "discount_25"}).json()
    assert disc["redemption"]["voucher_code"].startswith("AOEP-")
    assert disc["balance"] == bal0 - 500

    raffle = client.post("/rewards/redeem", headers=h, json={"prize_id": "raffle_ps5"}).json()
    assert raffle["redemption"]["raffle_entry_id"]
    assert raffle["redemption"]["detail"]["prize"] == "PlayStation 5"


def test_redeem_insufficient_points_400():
    h = _auth(_new_user("rw4@example.com"))
    r = client.post("/rewards/redeem", headers=h, json={"prize_id": "free_class"})
    assert r.status_code == 400


def test_redeem_unknown_prize_404():
    h = _auth(_new_user("rw5@example.com"))
    r = client.post("/rewards/redeem", headers=h, json={"prize_id": "nope"})
    assert r.status_code == 404
