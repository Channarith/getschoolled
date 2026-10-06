"""SuperGrok uses a subscription login and never leaks the token."""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO

import pytest

from aoep_shared.supergrok import (
    SUPERGROK_MODEL,
    SuperGrokUnavailable,
    subscription_reply,
    subscription_token,
)


def test_pytest_does_not_read_a_real_grok_login(monkeypatch):
    monkeypatch.delenv("SUPERGROK_TOKEN", raising=False)
    monkeypatch.delenv("XAI_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("GROK_AUTH_FILE", raising=False)
    assert subscription_token() == ""


def test_cli_auth_file_supplies_the_session(tmp_path, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text(
        json.dumps({"https://accounts.x.ai/sign-in": {"key": "session-token"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GROK_AUTH_FILE", str(auth))
    monkeypatch.delenv("SUPERGROK_TOKEN", raising=False)
    assert subscription_token() == "session-token"


def test_reply_posts_grok_4_7_to_the_subscription_proxy(monkeypatch):
    captured = {}

    def fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = {key.lower(): value for key, value in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))
        payload = {"choices": [{"message": {"content": "The stop line is here."}}]}
        return BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setenv("SUPERGROK_TOKEN", "secret-session")
    monkeypatch.setattr("urllib.request.urlopen", fake)
    text = subscription_reply(
        [{"role": "user", "content": "Where do I stop?"}],
        timeout_s=5,
    )
    assert text == "The stop line is here."
    assert captured["url"] == "https://cli-chat-proxy.grok.com/v1/chat/completions"
    assert captured["body"]["model"] == SUPERGROK_MODEL
    assert captured["headers"]["x-xai-token-auth"] == "xai-grok-cli"
    assert captured["headers"]["authorization"] == "Bearer secret-session"
    assert "secret-session" not in captured["body"]["messages"][0]["content"]


def test_proxy_refusal_names_the_status_and_not_the_token(monkeypatch):
    def fake(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url,
            403,
            "Forbidden",
            {},
            BytesIO(b'{"error":"tier"}'),
        )

    monkeypatch.setenv("SUPERGROK_TOKEN", "secret-session")
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(SuperGrokUnavailable) as caught:
        subscription_reply([{"role": "user", "content": "Hi"}], timeout_s=5)
    assert caught.value.status == 403
    assert "secret-session" not in str(caught.value)
    assert "tier" in str(caught.value)
