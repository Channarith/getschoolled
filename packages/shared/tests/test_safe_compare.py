"""Non-ASCII credentials must be rejected cleanly, never raise (they used to 500)."""

from __future__ import annotations

from aoep_shared import auth, internal_auth, totp, webhooks
from aoep_shared.flags import require_admin
from aoep_shared.provenance import (
    SignedManifest,
    build_manifest,
    sign_manifest,
    verify_manifest,
)
from aoep_shared.safe_compare import equals

KEY = b"k" * 32
WEIRD = "héllo 你好 \U0001f697 ខ្មែរ"


def test_equals_handles_non_ascii_and_none():
    assert equals(WEIRD, WEIRD) is True
    assert equals(WEIRD, "x") is False
    assert equals(None, "") is True
    assert equals("a", b"a") is True
    assert equals("\ud800", "x") is False


def test_bearer_token_with_non_ascii_signature_is_rejected():
    token = auth.sign_token({"sub": "u"}, KEY)
    raw = token.split(".")[0]
    assert auth.verify_token(f"{raw}.{WEIRD}", KEY) is None
    assert auth.verify_token(f"{WEIRD}.{token.split('.')[1]}", KEY) is None
    assert auth.verify_token(WEIRD, KEY) is None
    assert auth.verify_token(token, KEY) is not None


def test_internal_token_header_with_non_ascii_is_denied(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("INTERNAL_TOKEN", "secret")
    assert internal_auth.is_internal_caller(WEIRD) is False
    assert internal_auth.is_internal_caller("secret") is True


def test_admin_totp_webhook_and_manifest_reject_non_ascii():
    assert require_admin(WEIRD, "secret") is False
    assert totp.verify_totp("JBSWY3DPEHPK3PXP", "12345٣") is False
    assert webhooks.verify_signature(b"{}", WEIRD, "secret") is False
    signed = sign_manifest(build_manifest("a", "text"), KEY)
    forged = SignedManifest(signature=WEIRD, manifest=signed.manifest)
    assert verify_manifest(signed, KEY) is True
    assert verify_manifest(forged, KEY) is False
