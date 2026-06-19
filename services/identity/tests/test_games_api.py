"""Arcade games API: play -> score -> points -> leaderboard."""

from fastapi.testclient import TestClient
from identity.main import app

client = TestClient(app)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _user(email, name=""):
    return client.post("/auth/signup", json={
        "email": email, "password": "S3cretpass", "display_name": name}).json()["token"]


def test_catalog_lists_subjects_and_types():
    cat = client.get("/games").json()
    assert "biology" in cat["subjects"] and "programming" in cat["subjects"]
    assert {g["id"] for g in cat["game_types"]} == {"quiz", "speed", "match"}


def test_new_round_hides_answers():
    rnd = client.post("/games/new", json={"subject": "math", "game_type": "quiz", "n": 4}).json()
    assert rnd["game_id"] and len(rnd["items"]) == 4
    assert all("answer_index" not in it for it in rnd["items"])


def test_submit_requires_auth():
    rnd = client.post("/games/new", json={"subject": "math", "game_type": "quiz"}).json()
    assert client.post("/games/submit", json={"game_id": rnd["game_id"], "answers": {}}).status_code == 401


def test_play_awards_points_and_ranks():
    h = _auth(_user("gamer1@example.com", "Ada"))
    rnd = client.post("/games/new", json={"subject": "science", "game_type": "quiz", "n": 5}).json()
    # We don't know answers from the public round; submit empties first to verify 0,
    # then a fresh perfect round via the engine is covered in unit tests. Here we
    # assert the scoring/award/leaderboard plumbing on a real submission.
    answers = {it["id"]: 0 for it in rnd["items"]}
    out = client.post("/games/submit", headers=h,
                      json={"game_id": rnd["game_id"], "answers": answers}).json()
    assert "result" in out and "balance" in out
    assert out["points_earned"] == out["result"]["points"]
    assert out["balance"] >= out["points_earned"]
    # Player now appears on the leaderboard.
    board = client.get("/games/leaderboard").json()["leaders"]
    assert any(r["name"] == "Ada" for r in board)


def test_double_submit_blocked():
    h = _auth(_user("gamer2@example.com", "Lin"))
    rnd = client.post("/games/new", json={"subject": "history", "game_type": "quiz"}).json()
    body = {"game_id": rnd["game_id"], "answers": {it["id"]: 0 for it in rnd["items"]}}
    assert client.post("/games/submit", headers=h, json=body).status_code == 200
    assert client.post("/games/submit", headers=h, json=body).status_code == 409


def test_match_round_and_leaderboard_subject_filter():
    h = _auth(_user("gamer3@example.com", "Bo"))
    rnd = client.post("/games/new", json={"subject": "chemistry", "game_type": "match", "n": 4}).json()
    assert "terms" in rnd and "options" in rnd
    answers = {t["id"]: t["id"] for t in rnd["terms"]}  # perfect match
    out = client.post("/games/submit", headers=h,
                      json={"game_id": rnd["game_id"], "answers": answers}).json()
    assert out["result"]["accuracy"] == 1.0
    assert out["points_earned"] > 0
    board = client.get("/games/leaderboard", params={"subject": "chemistry"}).json()["leaders"]
    assert any(r["name"] == "Bo" for r in board)


def test_unknown_game_type_422():
    assert client.post("/games/new", json={"subject": "math", "game_type": "nope"}).status_code == 422
