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


def test_camera_always_allowed_mic_gated_by_floor():
    media = build_factory(load_config(env={})).media()
    # A regular attendee (no floor): camera + screen, but NOT microphone.
    listener = _decode_segment(
        media.issue_token(room="r", identity="a", can_publish=False).token.split(".")[1]
    )["video"]
    assert listener["canPublish"] is True
    assert "camera" in listener["canPublishSources"]
    assert "microphone" not in listener["canPublishSources"]
    # The floor holder additionally gets the microphone (one-speaker audio mutex).
    speaker = _decode_segment(
        media.issue_token(room="r", identity="b", can_publish=True).token.split(".")[1]
    )["video"]
    assert "camera" in speaker["canPublishSources"]
    assert "microphone" in speaker["canPublishSources"]


def test_token_signature_verifies_with_secret():
    cfg = load_config(env={"LIVEKIT_API_SECRET": "topsecret"})
    factory = build_factory(cfg)
    token = factory.media().issue_token(room="r", identity="i")
    signing_input, sig_seg = token.token.rsplit(".", 1)
    expected = hmac.new(b"topsecret", signing_input.encode(), hashlib.sha256).digest()
    padding = "=" * (-len(sig_seg) % 4)
    assert base64.urlsafe_b64decode(sig_seg + padding) == expected


def test_http_base_maps_ws_urls_to_https():
    from aoep_shared.providers.media import _BaseMediaProvider

    assert _BaseMediaProvider._http_base("wss://x.livekit.cloud") == "https://x.livekit.cloud"
    assert _BaseMediaProvider._http_base("ws://livekit:7880/") == "http://livekit:7880"
    assert _BaseMediaProvider._http_base("https://x.livekit.cloud/") == "https://x.livekit.cloud"


def test_verify_credentials_unreachable_without_url():
    cfg = load_config(env={"LIVEKIT_URL": ""})
    result = build_factory(cfg).media().verify_credentials(timeout=0.1)
    assert result["status"] == "unreachable"


def test_livekit_secret_whitespace_is_trimmed():
    # A trailing newline (common from kubectl/heredoc) must not change the token:
    # otherwise the HMAC signature silently mismatches and LiveKit rejects the WS.
    clean = load_config(env={"LIVEKIT_API_KEY": "APIabc", "LIVEKIT_API_SECRET": "s3cr3t"})
    dirty = load_config(
        env={"LIVEKIT_API_KEY": " APIabc\n", "LIVEKIT_API_SECRET": "s3cr3t\n"}
    )
    assert dirty.livekit_api_secret == "s3cr3t"
    assert dirty.livekit_api_key == "APIabc"
    tok_clean = build_factory(clean).media().issue_token(room="r", identity="i")
    tok_dirty = build_factory(dirty).media().issue_token(room="r", identity="i")
    # Same header+claims signing input -> identical signature once trimmed.
    assert tok_clean.token.rsplit(".", 1)[1] == tok_dirty.token.rsplit(".", 1)[1]


def test_livekit_whitespace_only_secret_falls_back_to_default():
    cfg = load_config(env={"LIVEKIT_API_SECRET": "   \n"})
    assert cfg.livekit_api_secret == "devsecret"


def test_self_hosted_dev_defaults_keep_url():
    # A local ``--dev`` LiveKit container legitimately uses devkey/devsecret, so  # pragma: allowlist secret
    # a self-hosted URL must still be handed to clients.
    token = build_factory(load_config(env={})).media().issue_token(room="r", identity="i")
    assert token.url == "ws://livekit:7880"


def test_cloud_url_with_dev_creds_yields_no_url():
    # Cloud endpoint but still on dev defaults -> Cloud will reject the token, so
    # suppress the URL and let the client skip a doomed WebSocket connection.
    cfg = load_config(env={"LIVEKIT_URL": "wss://demo.livekit.cloud"})
    token = build_factory(cfg).media().issue_token(room="r", identity="i")
    assert token.url == ""


def test_cloud_url_with_real_creds_keeps_url():
    cfg = load_config(
        env={
            "LIVEKIT_URL": "wss://demo.livekit.cloud",
            "LIVEKIT_API_KEY": "APIrealkey",
            "LIVEKIT_API_SECRET": "realsecretvalue",
        }
    )
    token = build_factory(cfg).media().issue_token(room="r", identity="i")
    assert token.url == "wss://demo.livekit.cloud"
