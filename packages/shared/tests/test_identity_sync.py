"""identity_base_url() resolution (admin check / rewards depend on this)."""

from aoep_shared.identity_sync import identity_base_url


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
