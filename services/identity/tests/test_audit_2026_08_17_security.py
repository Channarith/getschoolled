"""Regressions for the 2026-08-17 audit of docs/audit-2026-08-16.txt findings.

Each test reproduces an exploit that worked against the service before the fix,
so a revert fails here rather than in production.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from aoep_shared.totp import totp_at
from identity.main import app

client = TestClient(app)


def _signup(email: str, password: str = "Sup3rSecret!23") -> str:
    r = client.post(
        "/auth/signup",
        json={"email": email, "password": password, "display_name": "Audit"},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _code(secret: str) -> str:
    return totp_at(secret, counter=int(time.time() // 30))


# --------------------------------------------------------------------------- #
# CRIT-26 — self-reported practice XP was unbounded and redeemable for cash
# --------------------------------------------------------------------------- #

def test_practice_xp_cannot_exceed_the_reported_set_size():
    """`correct` is clamped to `total`, so a forged payload mints nothing."""
    tok = _signup("audit-practice-forge@example.com")
    r = client.post(
        "/language/practice",
        json={"language": "en", "skill": "pronunciation", "correct": 1_000_000, "total": 0},
        headers=_auth(tok),
    )
    assert r.status_code == 200, r.text
    assert r.json()["xp"] == 0, "a set with zero items must award zero XP"
    assert r.json()["balance"] == 0

    # Over-reporting against a real set is clamped to that set's maximum.
    r = client.post(
        "/language/practice",
        json={"language": "en", "skill": "pronunciation", "correct": 999, "total": 10},
        headers=_auth(tok),
    )
    honest_max = client.post(
        "/language/practice",
        json={"language": "en", "skill": "pronunciation", "correct": 10, "total": 10},
        headers=_auth(_signup("audit-practice-honest@example.com")),
    )
    assert r.json()["xp"] == honest_max.json()["xp"]


def test_forged_practice_cannot_fund_a_gift_card():
    """The end-to-end exploit: self-report -> redeem a real-money prize."""
    tok = _signup("audit-practice-giftcard@example.com")
    client.post(
        "/language/practice",
        json={"language": "en", "skill": "pronunciation", "correct": 10_000_000, "total": 0},
        headers=_auth(tok),
    )
    r = client.post("/rewards/redeem", json={"prize_id": "gift_amazon_25"}, headers=_auth(tok))
    assert r.status_code == 400, "forged practice must not fund a gift card"
    assert "insufficient" in r.json()["detail"].lower()


def test_honest_practice_still_awards_and_persists():
    tok = _signup("audit-practice-legit@example.com")
    r = client.post(
        "/language/practice",
        json={"language": "es", "skill": "vocabulary", "correct": 5, "total": 5},
        headers=_auth(tok),
    )
    assert r.status_code == 200, r.text
    assert r.json()["xp"] > 0
    assert r.json()["balance"] == r.json()["xp"]


# --------------------------------------------------------------------------- #
# HIGH-27a/b — non-session tokens were accepted as full session tokens
# --------------------------------------------------------------------------- #

def test_password_reset_token_is_not_a_session_token():
    email = "audit-reset-token@example.com"
    _signup(email)
    reset = client.post("/auth/forgot-password", json={"email": email}).json()["reset_token"]

    assert client.get("/auth/me", headers=_auth(reset)).status_code == 401
    assert client.get("/rewards", headers=_auth(reset)).status_code == 401
    assert client.post("/enrollments", json={"course_id": "x"}, headers=_auth(reset)).status_code == 401

    # ...but it still does the one job it was minted for.
    used = client.post(
        "/auth/reset-password", json={"token": reset, "new_password": "An0therPass!45"}
    )
    assert used.status_code == 200, used.text


def test_profile_share_token_is_not_a_session_token():
    tok = _signup("audit-share-token@example.com")
    sid = client.post(
        "/students", json={"display_name": "Kid", "age": 9}, headers=_auth(tok)
    ).json()["id"]
    grant = client.post(
        f"/students/{sid}/profile-share-grants",
        json={"integration": "partner", "scopes": ["mastery"], "ttl_s": 86_400},
        headers=_auth(tok),
    )
    assert grant.status_code == 200, grant.text
    share = grant.json()["token"]

    assert client.get("/auth/me", headers=_auth(share)).status_code == 401
    assert client.get("/rewards", headers=_auth(share)).status_code == 401
    # Critically: it must not be able to mint fresh grants, which would make
    # grant revocation meaningless.
    assert client.post(
        f"/students/{sid}/profile-share-grants",
        json={"integration": "x", "scopes": ["mastery"], "ttl_s": 86_400},
        headers=_auth(share),
    ).status_code == 401

    # The scoped read it exists for still works.
    assert client.get("/profile-shares/context", headers=_auth(share)).status_code == 200


# --------------------------------------------------------------------------- #
# HIGH-28 — /auth/2fa/setup silently switched active 2FA back off
# --------------------------------------------------------------------------- #

def test_resetup_cannot_disable_active_2fa_without_a_code():
    email = "audit-2fa-resetup@example.com"
    tok = _signup(email)
    secret = client.post("/auth/2fa/setup", json={}, headers=_auth(tok)).json()["secret"]
    assert client.post(
        "/auth/2fa/confirm", json={"code": _code(secret)}, headers=_auth(tok)
    ).status_code == 200

    denied = client.post("/auth/2fa/setup", json={}, headers=_auth(tok))
    assert denied.status_code == 400, "re-provisioning must require a current code"

    login = client.post("/auth/login", json={"email": email, "password": "Sup3rSecret!23"})
    assert login.json().get("requires_2fa") is True, "2FA must still be enforced"

    # A genuine re-provision (user has their authenticator) is still allowed.
    assert client.post(
        "/auth/2fa/setup", json={"code": _code(secret)}, headers=_auth(tok)
    ).status_code == 200


# --------------------------------------------------------------------------- #
# HIGH-29 — the 2FA lockout was keyed on a token that changed every login
# --------------------------------------------------------------------------- #

def test_2fa_lockout_survives_re_login():
    from identity import auth_security

    email = "audit-2fa-lockout@example.com"
    tok = _signup(email)
    secret = client.post("/auth/2fa/setup", json={}, headers=_auth(tok)).json()["secret"]
    client.post("/auth/2fa/confirm", json={"code": _code(secret)}, headers=_auth(tok))

    # Simulate the bypass directly: a brand-new mfa_token for every guess, which
    # is what re-logging in used to buy the attacker.
    limit = auth_security.MFA_MAX_ACCOUNT_FAILURES
    statuses = []
    for i in range(limit + 2):
        login = client.post("/auth/login", json={"email": email, "password": "Sup3rSecret!23"})
        mfa = login.json().get("mfa_token")
        assert mfa, login.text
        # Burn-avoidance: give each attempt a distinct token the way a real
        # attacker would by re-logging in a second later.
        auth_security._mfa_fail_counts.pop(mfa, None)
        auth_security._mfa_burned.discard(mfa)
        statuses.append(client.post(
            "/auth/2fa/verify", json={"mfa_token": mfa, "code": f"{i:06d}"}
        ).status_code)

    assert 429 in statuses, (
        "account-scoped 2FA lockout never engaged; re-login still grants "
        f"unlimited guesses (statuses={statuses})"
    )
    assert statuses.index(429) <= limit


# --------------------------------------------------------------------------- #
# MED-30 — a phone number satisfied the payment gate
# --------------------------------------------------------------------------- #

def test_phone_only_profile_does_not_validate_billing():
    tok = _signup("audit-phone-billing@example.com")
    before = client.get("/auth/onboarding-status", headers=_auth(tok)).json()
    assert before["billing_validated"] is False

    r = client.post("/onboarding/profile", json={"phone": "555-1234"}, headers=_auth(tok))
    assert r.status_code == 200, r.text

    after = client.get("/auth/onboarding-status", headers=_auth(tok)).json()
    assert after["billing_validated"] is False, (
        "supplying a phone number must not mark billing as validated"
    )
