"""Regression tests for the 2026-08-17 extensive bug audit (identity service).

Each test pins one audited defect:
- CRIT-26  /language/practice minted unbounded self-reported points.
- HIGH-27a password-reset tokens acted as full session tokens.
- HIGH-27b profile-share tokens acted as full session tokens.
- HIGH-28  /auth/2fa/setup silently disabled active 2FA with no second factor.
- HIGH-29  2FA brute-force lockout reset on every re-login (keyed on mfa_token).
- MED-30   saving a phone number marked billing as validated.
- MED-31   /enrollments/{id}/status took the score from the request body even
           when a signed pass_decision_token carried the authoritative score.
"""

from fastapi.testclient import TestClient

from identity.main import app

client = TestClient(app)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _new_user(email):
    return client.post(
        "/auth/signup", json={"email": email, "password": "S3cretpass"}
    ).json()["token"]


# CRIT-26 -------------------------------------------------------------------- #

def test_language_practice_points_are_bounded():
    h = _auth(_new_user("audit26a@example.com"))
    out = client.post(
        "/language/practice", headers=h,
        json={"language": "en", "skill": "pronunciation", "correct": 1000000, "total": 0},
    ).json()
    # 500-item cap -> 500 * 8 * 1.25 = 5000 max for a hard skill.
    assert out["xp"] <= 5000
    assert out["balance"] <= 5000


def test_language_practice_correct_clamped_to_total():
    h = _auth(_new_user("audit26b@example.com"))
    out = client.post(
        "/language/practice", headers=h,
        json={"language": "en", "skill": "vocabulary", "correct": 400, "total": 5},
    ).json()
    # correct clamped to total=5 -> 5*8 + 16 (perfect-set bonus) = 56.
    assert out["xp"] == 56


# HIGH-27a ------------------------------------------------------------------- #

def test_password_reset_token_is_not_a_session():
    _new_user("audit27a@example.com")
    forgot = client.post(
        "/auth/forgot-password", json={"email": "audit27a@example.com"}).json()
    reset_token = forgot["reset_token"]
    me = client.get("/auth/me", headers=_auth(reset_token))
    assert me.status_code == 401
    # And the reset flow itself still works.
    ok = client.post("/auth/reset-password", json={
        "token": reset_token, "new_password": "Newpass12"})
    assert ok.status_code == 200


# HIGH-27b ------------------------------------------------------------------- #

def test_profile_share_token_is_not_a_session():
    h = _auth(_new_user("audit27b@example.com"))
    student = client.post(
        "/students", headers=h, json={"display_name": "Learner S"}).json()
    grant = client.post(
        f"/students/{student['id']}/profile-share-grants", headers=h,
        json={"integration": "robot-tutor", "scopes": ["mastery"], "ttl_s": 600},
    ).json()
    me = client.get("/auth/me", headers=_auth(grant["token"]))
    assert me.status_code == 401
    # The share token still works for its actual purpose.
    shared = client.get("/profile-shares/context", headers=_auth(grant["token"]))
    assert shared.status_code == 200


# HIGH-28 -------------------------------------------------------------------- #

def test_2fa_setup_does_not_disable_active_2fa():
    from aoep_shared.totp import current_totp

    tok = _new_user("audit28@example.com")
    h = _auth(tok)
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    code = current_totp(secret)
    client.post("/auth/2fa/confirm", headers=h, json={"code": code})

    # Setup on an enabled account must refuse, not silently downgrade.
    again = client.post("/auth/2fa/setup", headers=h)
    assert again.status_code == 409

    # Login still requires the second factor.
    step1 = client.post("/auth/login", json={
        "email": "audit28@example.com", "password": "S3cretpass"}).json()
    assert step1.get("requires_2fa") is True


# HIGH-29 -------------------------------------------------------------------- #

def test_2fa_lockout_survives_relogin():
    from aoep_shared.totp import current_totp

    tok = _new_user("audit29@example.com")
    h = _auth(tok)
    secret = client.post("/auth/2fa/setup", headers=h).json()["secret"]
    client.post("/auth/2fa/confirm", headers=h,
                json={"code": current_totp(secret)})

    def fresh_mfa_token():
        step1 = client.post("/auth/login", json={
            "email": "audit29@example.com", "password": "S3cretpass"}).json()
        return step1["mfa_token"]

    # Five wrong codes spread across FIVE different mfa tokens (a re-login
    # between each) must still engage the lockout.
    last_token = ""
    for _ in range(5):
        last_token = fresh_mfa_token()
        out = client.post("/auth/2fa/verify",
                          json={"mfa_token": last_token, "code": "000000"})
        assert out.status_code == 401

    # The fifth failure burned the token...
    burned = client.post("/auth/2fa/verify",
                         json={"mfa_token": last_token, "code": current_totp(secret)})
    assert burned.status_code == 401
    # ...and the account-level counter persists: the very next wrong code on a
    # brand-new token immediately burns that token too.
    sixth = fresh_mfa_token()
    client.post("/auth/2fa/verify", json={"mfa_token": sixth, "code": "000000"})
    replay = client.post("/auth/2fa/verify",
                         json={"mfa_token": sixth, "code": current_totp(secret)})
    assert replay.status_code == 401


# MED-30 --------------------------------------------------------------------- #

def test_phone_number_does_not_validate_billing():
    h = _auth(_new_user("audit30@example.com"))
    out = client.post("/onboarding/profile", headers=h,
                      json={"display_name": "P", "phone": "555-1234"})
    assert out.status_code == 200
    status = client.get("/auth/onboarding-status", headers=h).json()
    assert status["billing_validated"] is False


# HIGH-16 (consent proxy) ---------------------------------------------------- #

def test_consent_requires_auth():
    out = client.post("/consent", json={"scope": "face_recognition", "granted": True})
    assert out.status_code == 401


def test_consent_forwards_to_memory_with_real_student(monkeypatch):
    import json as _json

    import identity.main as identity_main

    monkeypatch.setattr(identity_main.app.state.config, "memory_base_url", "http://memory.test")
    captured = {}

    class _Resp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = _json.loads(req.data.decode())
        captured["internal"] = req.headers.get("X-internal-token", "")
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    h = _auth(_new_user("audit-consent@example.com"))
    out = client.post("/consent", headers=h,
                      json={"scope": "face_recognition", "granted": True, "region": "us"})
    assert out.status_code == 200, out.text
    assert captured["url"] == "http://memory.test/consent"
    # The literal "current-user" placeholder is gone — a real id is stored.
    assert captured["body"]["student_id"] != "current-user"
    assert captured["body"]["student_id"] == out.json()["student_id"]
    assert captured["internal"], "internal service token not attached"


def test_consent_rejects_foreign_student(monkeypatch):
    import identity.main as identity_main

    monkeypatch.setattr(identity_main.app.state.config, "memory_base_url", "http://memory.test")
    h = _auth(_new_user("audit-consent2@example.com"))
    out = client.post("/consent", headers=h, json={
        "scope": "recording", "granted": True, "student_id": "someone-else"})
    assert out.status_code == 403


# Voucher TOCTOU + LOW-32 ---------------------------------------------------- #

def test_voucher_consume_rechecks_validity():
    import identity.main as identity_main

    store = identity_main._voucher_store()
    store.create(code="AUDIT-TOCTOU", kind="coupon", value=10.0, max_uses=1)
    store.consume("AUDIT-TOCTOU")  # first and only use
    try:
        store.consume("AUDIT-TOCTOU")
        raise AssertionError("second consume past max_uses succeeded")
    except ValueError:
        pass


def test_class_scoped_free_pass_requires_the_class():
    import identity.main as identity_main

    store = identity_main._voucher_store()
    store.create(code="AUDIT-PASS", kind="free_pass", value=0.0, max_uses=5,
                 class_id="algebra-101")
    # Omitting class_id must not bypass the restriction.
    try:
        store.validate("AUDIT-PASS", 49.0)
        raise AssertionError("class-scoped free pass validated without class_id")
    except ValueError:
        pass
    # Wrong class rejected, right class works.
    try:
        store.validate("AUDIT-PASS", 49.0, class_id="chem-999")
        raise AssertionError("class-scoped free pass validated for another class")
    except ValueError:
        pass
    v, final, _ = store.validate("AUDIT-PASS", 49.0, class_id="algebra-101")
    assert final == 0.0


# MED-31 --------------------------------------------------------------------- #

def test_pass_decision_token_score_overrides_body_score():
    from aoep_shared.auth import sign_token

    h = _auth(_new_user("audit31@example.com"))
    me = client.get("/auth/me", headers=h).json()
    student_id = me["students"][0]["id"] if me.get("students") else None
    if student_id is None:
        student = client.post(
            "/students", headers=h, json={"display_name": "L"}).json()
        student_id = student["id"]
    client.post("/enrollments", headers=h, json={"course_id": "c7", "title": "C7"})

    import identity.main as identity_main
    token = sign_token(
        {"kind": "assessment_pass", "student_id": student_id,
         "course_id": "c7", "score": 0.51},
        identity_main._assessment_signing_key(), ttl_s=600)

    out = client.post(
        "/enrollments/c7/status", headers=h,
        json={"status": "passed", "score": 1.0, "level": "advanced",
              "hands_on": True, "pass_decision_token": token},
    ).json()
    # The signed score (0.51) wins over the body score (1.0).
    assert out["score"] == 0.51
