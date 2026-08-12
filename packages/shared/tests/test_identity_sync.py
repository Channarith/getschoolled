"""identity_base_url() resolution (admin check / rewards depend on this)."""

from aoep_shared.identity_sync import identity_base_url, internal_token


def test_identity_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("IDENTITY_URL", "http://identity:8000/")
    monkeypatch.setenv("IDENTITY_ORIGIN", "http://other:9000")
    assert identity_base_url() == "http://identity:8000"


def test_falls_back_to_identity_origin(monkeypatch):
    # The cluster config historically set only IDENTITY_ORIGIN; the helper must
    # honor it so server-to-server admin checks don't hit localhost and 403.
    monkeypatch.delenv("IDENTITY_URL", raising=False)
    monkeypatch.setenv("IDENTITY_ORIGIN", "http://identity:8000")
    assert identity_base_url() == "http://identity:8000"


def test_default_localhost_when_unset(monkeypatch):
    monkeypatch.delenv("IDENTITY_URL", raising=False)
    monkeypatch.delenv("IDENTITY_ORIGIN", raising=False)
    assert identity_base_url() == "http://localhost:8008"


def test_internal_token_prefers_static(monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "static-a")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "legacy-b")
    assert internal_token() == "static-a"


def test_internal_token_falls_back_to_service_alias(monkeypatch):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "legacy-b")
    monkeypatch.delenv("INTERNAL_TOKEN_KEY", raising=False)
    assert internal_token() == "legacy-b"


def test_internal_token_mints_hmac_when_key_set(monkeypatch):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)
    monkeypatch.setenv("INTERNAL_TOKEN_KEY", "unit-test-internal-key")
    tok = internal_token()
    assert tok
    assert tok != "dev-internal-token"
    from aoep_shared.auth import verify_token

    claims = verify_token(tok, b"unit-test-internal-key")
    assert claims is not None
    assert claims.get("scope") == "internal"
