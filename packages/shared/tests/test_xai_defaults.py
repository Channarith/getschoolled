from __future__ import annotations

import io
import urllib.error

from aoep_shared.config import AppConfig, load_config
from aoep_shared.xai_grok_voice import XAI_DEFAULT_MODEL, _http_post
from aoep_shared.xai_voice import XAIVoiceClient, make_client_from_config


def test_shared_xai_defaults_do_not_use_retired_model() -> None:
    assert AppConfig().xai_model == "grok-4.3"
    assert load_config({}).xai_model == "grok-4.3"
    assert XAI_DEFAULT_MODEL == "grok-4.3"
    assert XAIVoiceClient._DEFAULT_MODEL == "grok-4.3"
    assert "grok-2-1212" not in {
        AppConfig().xai_model,
        load_config({}).xai_model,
        XAI_DEFAULT_MODEL,
        XAIVoiceClient._DEFAULT_MODEL,
    }


def test_xai_client_from_config_uses_current_default() -> None:
    client = make_client_from_config(load_config({"XAI_API_KEY": "test-key"}))
    assert client._model == "grok-4.3"


def test_grok_http_error_includes_model_and_body(monkeypatch) -> None:
    def raise_http_error(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            url="https://api.x.ai/v1/chat/completions",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(b'{"error":"model retired"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", raise_http_error)
    try:
        _http_post(
            "https://api.x.ai/v1/chat/completions",
            {"model": "grok-4.3"},
            "test-key",
        )
    except RuntimeError as exc:
        message = str(exc)
        assert "grok-4.3" in message
        assert "model retired" in message
    else:
        raise AssertionError("expected RuntimeError")
