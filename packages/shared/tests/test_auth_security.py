"""Secure auth: TOTP, password reset, OAuth sandbox, login audit."""

import time

from aoep_shared.login_audit import login_context_from_headers
from aoep_shared.oauth_login import OAuthError, verify_facebook_access_token, verify_google_id_token
from aoep_shared.password_reset import issue_reset_token, verify_reset_token
from aoep_shared.totp import current_totp, generate_totp_secret, verify_totp


def test_totp_roundtrip():
    secret = generate_totp_secret()
    code = current_totp(secret)
    assert verify_totp(secret, code)


def test_password_reset_token():
    key = b"test-key"
    tok = issue_reset_token("acct1", "a@b.com", key, ttl_s=60)
    body = verify_reset_token(tok, key)
    assert body and body["sub"] == "acct1"


def test_login_context_from_proxy_headers():
    ctx = login_context_from_headers(
        x_forwarded_for="203.0.113.1, 10.0.0.1",
        cf_ipcountry="us",
        user_agent="Mozilla/5.0",
    )
    assert ctx.ip == "203.0.113.1"
    assert ctx.country_hint == "US"


def test_google_sandbox_token():
    ident = verify_google_id_token("sandbox_google_alice@example.com")
    assert ident["email"] == "alice@example.com"


def test_facebook_sandbox_token():
    ident = verify_facebook_access_token("sandbox_facebook_bob@example.com")
    assert ident["email"] == "bob@example.com"
