"""Secure login: forgot password, 2FA, OAuth, passkeys, login audit."""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _signup(email="sec@example.com", password="S3cretpass"):
    return client.post("/auth/signup", json={"email": email, "password": password,
                                             "display_name": "Sec"}).json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_forgot_and_reset_password():
    tok = _signup("reset@example.com")["token"]
    forgot = client.post("/auth/forgot-password", json={"email": "reset@example.com"}).json()
    assert forgot["sent"] is True
    assert "reset_token" in forgot
    ok = client.post("/auth/reset-password", json={
        "token": forgot["reset_token"], "new_password": "Newpass12",
    })
    assert ok.status_code == 200
    login = client.post("/auth/login", json={"email": "reset@example.com", "password": "Newpass12"})
    assert login.status_code == 200


def test_2fa_login_flow():
    tok = _signup("mfa@example.com")["token"]
    h = _auth(tok)
    setup = client.post("/auth/2fa/setup", headers=h).json()
    from aoep_shared.totp import current_totp
    code = current_totp(setup["secret"])
    client.post("/auth/2fa/confirm", headers=h, json={"code": code})
    step1 = client.post("/auth/login", json={"email": "mfa@example.com", "password": "S3cretpass"}).json()
    assert step1.get("requires_2fa")
    step2 = client.post("/auth/2fa/verify", json={"mfa_token": step1["mfa_token"], "code": code}).json()
    assert step2.get("token")


def test_google_oauth_sandbox():
    out = client.post("/auth/oauth/google", json={
        "id_token": "sandbox_google_oauth@example.com",
    }).json()
    assert out["token"]
    assert out["account"]["email"] == "oauth@example.com"


def test_login_history_recorded():
    _signup("hist@example.com")
    client.post("/auth/login", json={"email": "hist@example.com", "password": "S3cretpass"},
                headers={"User-Agent": "TestBrowser/1.0", "X-Forwarded-For": "198.51.100.9"})
    tok = client.post("/auth/login", json={"email": "hist@example.com", "password": "S3cretpass"}).json()["token"]
    hist = client.get("/auth/login-history", headers=_auth(tok)).json()
    assert len(hist["events"]) >= 1
    assert any(e.get("ip") == "198.51.100.9" for e in hist["events"])


def test_passkey_register_and_login():
    tok = _signup("pk@example.com")["token"]
    h = _auth(tok)
    opts = client.post("/auth/passkey/register/options", headers=h).json()
    reg = client.post("/auth/passkey/register/verify", headers=h, json={
        "challenge": opts["challenge"],
        "credential_id": "cred-test-1",
        "client_data_json": '{"type":"webauthn.create"}',
    })
    assert reg.status_code == 200
    login_opts = client.post("/auth/passkey/login/options", json={"email": "pk@example.com"}).json()
    login = client.post("/auth/passkey/login/verify", json={
        "account_id": login_opts["account_id"],
        "challenge": login_opts["challenge"],
        "credential_id": "cred-test-1",
        "client_data_json": '{"type":"webauthn.get"}',
    }).json()
    assert login.get("token")
