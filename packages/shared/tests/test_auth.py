"""Auth primitives: password hashing + session tokens."""

import time

from aoep_shared.auth import (
    hash_password,
    sign_token,
    verify_password,
    verify_token,
)

KEY = b"test-auth-key"


def test_password_hash_and_verify():
    enc = hash_password("S3cret!pass")
    assert enc.startswith("pbkdf2_sha256$")
    assert verify_password("S3cret!pass", enc) is True
    assert verify_password("wrong", enc) is False


def test_password_hash_is_salted():
    a = hash_password("same-password")
    b = hash_password("same-password")
    assert a != b  # random salt
    assert verify_password("same-password", a)
    assert verify_password("same-password", b)


def test_empty_password_rejected():
    import pytest

    with pytest.raises(ValueError):
        hash_password("")


def test_token_roundtrip():
    tok = sign_token({"sub": "acct-1", "email": "a@b.c"}, KEY)
    claims = verify_token(tok, KEY)
    assert claims and claims["sub"] == "acct-1" and claims["email"] == "a@b.c"


def test_token_tampered_or_wrong_key():
    tok = sign_token({"sub": "x"}, KEY)
    assert verify_token(tok, b"other-key") is None
    assert verify_token(tok + "junk", KEY) is None
    assert verify_token("not-a-token", KEY) is None


def test_token_expiry():
    tok = sign_token({"sub": "x"}, KEY, ttl_s=1)
    assert verify_token(tok, KEY, now=time.time() + 10) is None  # expired
    assert verify_token(tok, KEY, now=time.time()) is not None
