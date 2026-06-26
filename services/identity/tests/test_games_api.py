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
    assert "wordplay" in cat["subjects"]
    ids = {g["id"] for g in cat["game_types"]}
    assert "quiz" in ids and "tiles" in ids and "farm" in ids


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


def test_marathon_round_via_api():
    rnd = client.post("/games/new", json={
        "subject": "math", "game_type": "marathon", "n": 20,
    }).json()
    assert rnd["game_type"] == "marathon"
    assert len(rnd["items"]) == 15
    assert rnd["time_limit_s"] == 180


def test_catalog_includes_age_groups():
    cat = client.get("/games").json()
    assert {a["id"] for a in cat["age_groups"]} == {"kids", "tween", "teen", "adult"}


def test_catalog_locale_query():
    cat = client.get("/games", params={"locale": "es"}).json()
    assert cat["subjects_localized"]
    tiles = next(g for g in cat["game_types"] if g["id"] == "tiles")
    assert tiles["name"] != "Word Tiles"


def test_new_game_extended_locale():
    rnd = client.post("/games/new", json={
        "subject": "etiquette", "game_type": "doing", "locale": "es", "n": 3,
    }).json()
    assert rnd["locale"] == "es"
    assert len(rnd["items"]) >= 1


def test_kids_round_and_age_leaderboard():
    h = _auth(_user("kiddo@example.com", "Kiddo"))
    rnd = client.post("/games/new", json={
        "subject": "math", "game_type": "quiz", "age_group": "kids", "n": 4}).json()
    assert rnd["age_group"] == "kids"
    out = client.post("/games/submit", headers=h,
                      json={"game_id": rnd["game_id"], "answers": {it["id"]: 1 for it in rnd["items"]}}).json()
    assert "points_earned" in out
    board = client.get("/games/leaderboard", params={"age_group": "kids"}).json()
    assert board["age_group"] == "kids"
    assert any(r["name"] == "Kiddo" for r in board["leaders"])


def test_unknown_age_group_422():
    assert client.post("/games/new", json={
        "subject": "math", "game_type": "quiz", "age_group": "elder"}).status_code == 422


def test_language_practice_awards_points():
    h = _auth(_user("polyglot@example.com", "Poly"))
    out = client.post("/language/practice", headers=h, json={
        "language": "es", "skill": "pronunciation", "correct": 5, "total": 5}).json()
    assert out["xp"] > 0
    assert out["balance"] >= out["xp"]
    # Shows up in the rewards ledger.
    rw = client.get("/rewards", headers=h).json()
    assert any(e["reason"] == "language:es" for e in rw["ledger"])


def test_language_practice_requires_auth():
    assert client.post("/language/practice", json={
        "language": "fr", "skill": "vocabulary", "correct": 3, "total": 5}).status_code == 401
