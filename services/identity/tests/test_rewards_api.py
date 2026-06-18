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


def test_redeem_discount_and_raffle():
    h = _auth(_new_user("rw3@example.com"))
    # Earn enough points: pass several advanced courses.
    for i in range(3):
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
