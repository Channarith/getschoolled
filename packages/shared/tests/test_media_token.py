"""LiveKit-style token minting is identical across local/cloud (only URL/keys differ)."""

import base64
import hashlib
import hmac
import json

from aoep_shared.config import load_config
from aoep_shared.factory import build_factory


def _decode_segment(segment: str) -> dict:
    padding = "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment + padding))


def test_token_has_valid_structure_and_claims():
    factory = build_factory(load_config(env={}))
    token = factory.media().issue_token(room="class-1", identity="student-7")
    assert token.room == "class-1"
    header_seg, claims_seg, sig_seg = token.token.split(".")
    header = _decode_segment(header_seg)
    claims = _decode_segment(claims_seg)
    assert header["alg"] == "HS256"
    assert claims["sub"] == "student-7"
    assert claims["video"]["room"] == "class-1"


def test_token_signature_verifies_with_secret():
    cfg = load_config(env={"LIVEKIT_API_SECRET": "topsecret"})
    factory = build_factory(cfg)
    token = factory.media().issue_token(room="r", identity="i")
    signing_input, sig_seg = token.token.rsplit(".", 1)
    expected = hmac.new(b"topsecret", signing_input.encode(), hashlib.sha256).digest()
    padding = "=" * (-len(sig_seg) % 4)
    assert base64.urlsafe_b64decode(sig_seg + padding) == expected
