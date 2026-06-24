"""Identity service: signup/login/me, password change, portfolio."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="a@example.com", password="S3cretpass"):
    return client.post("/auth/signup", json={"email": email, "password": password,
                                             "display_name": "Alex"}).json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_signup_login_me():
    out = _signup("login@example.com")
    assert out["token"] and out["account"]["email"] == "login@example.com"

    login = client.post("/auth/login", json={"email": "login@example.com", "password": "S3cretpass"}).json()
    assert login["token"]

    me = client.get("/auth/me", headers=_auth(login["token"])).json()
    assert me["email"] == "login@example.com"
    assert me["tier"] == "free"


def test_duplicate_email_rejected():
    _signup("dup@example.com")
    r = client.post("/auth/signup", json={"email": "dup@example.com", "password": "x12345678"})
    assert r.status_code == 400


def test_login_wrong_password_401():
    _signup("wp@example.com")
    r = client.post("/auth/login", json={"email": "wp@example.com", "password": "nope"})
    assert r.status_code == 401


def test_me_requires_valid_token():
    assert client.get("/auth/me").status_code in (401, 422)
    assert client.get("/auth/me", headers=_auth("bad.token")).status_code == 401


def test_password_change():
    tok = _signup("pc@example.com")["token"]
    bad = client.post("/auth/password", headers=_auth(tok),
                      json={"current_password": "wrong", "new_password": "newpass12"})
    assert bad.status_code == 400
    ok = client.post("/auth/password", headers=_auth(tok),
                     json={"current_password": "S3cretpass", "new_password": "newpass12"})
    assert ok.status_code == 200
    # New password works for login.
    assert client.post("/auth/login", json={"email": "pc@example.com", "password": "newpass12"}).status_code == 200


def test_portfolio_enroll_and_status():
    tok = _signup("port@example.com")["token"]
    h = _auth(tok)
    client.post("/enrollments", headers=h, json={"course_id": "c1", "title": "Intro Bio"})
    client.post("/enrollments", headers=h, json={"course_id": "c2", "title": "Algebra"})
    client.post("/enrollments/c1/status", headers=h, json={"status": "passed", "score": 0.92})
    client.post("/enrollments/c2/status", headers=h, json={"status": "failed", "score": 0.4})

    pf = client.get("/portfolio", headers=h).json()
    assert pf["counts"].get("passed") == 1
    assert pf["counts"].get("failed") == 1
    passed = pf["by_status"]["passed"][0]
    assert passed["course_id"] == "c1" and passed["score"] == 0.92


def test_membership_tier_change():
    tok = _signup("tier@example.com")["token"]
    out = client.post("/membership/tier", headers=_auth(tok), json={"tier": "pro"}).json()
    assert out["tier"] == "pro"


def test_status_update_requires_enrollment():
    tok = _signup("noenr@example.com")["token"]
    r = client.post("/enrollments/ghost/status", headers=_auth(tok), json={"status": "passed"})
    assert r.status_code == 404


def test_admin_accounts_forbidden_for_regular_user():
    tok = _signup("regular@test.com")["token"]
    assert client.get("/admin/accounts", headers=_auth(tok)).status_code == 403


def test_admin_accounts_list_for_operator():
    app.state.accounts.seed_admin(
        "operator@test.com", "Secret123", username="operator",
    )
    tok = client.post("/auth/login", json={"email": "operator@test.com", "password": "Secret123"}).json()["token"]
    r = client.get("/admin/accounts", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(a["email"] == "operator@test.com" for a in body["accounts"])
