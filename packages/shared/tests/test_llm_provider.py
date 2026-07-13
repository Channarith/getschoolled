"""OpenAI-compatible LLM provider: real HTTP shape, streaming, Nemotron agent."""

from __future__ import annotations

import json

import pytest

from aoep_shared.config import load_config
from aoep_shared.factory import ProviderFactory
from aoep_shared.providers import llm as llm_mod
from aoep_shared.providers.base import ChatMessage
from aoep_shared.providers.llm import (
    CloudLLMProvider,
    LLMError,
    NemotronLLMProvider,
    nemotron_configured,
)


class _FakeResp:
    def __init__(self, *, body: bytes = b"", lines=None):
        self._body = body
        self._lines = lines or []

    def read(self):
        return self._body

    def __iter__(self):
        return iter(self._lines)


def _patch_urlopen(monkeypatch, *, capture: dict, resp: _FakeResp):
    def fake_urlopen(req, timeout=None):
        capture["url"] = req.full_url
        capture["headers"] = dict(req.headers)
        capture["body"] = json.loads(req.data.decode("utf-8"))
        return resp

    monkeypatch.setattr(llm_mod.urllib.request, "urlopen", fake_urlopen)


def _cfg(**env):
    base = {"LLM_BASE_URL": "http://llm:8000/v1", "LLM_MODEL": "edu-1"}
    base.update(env)
    return load_config(base)


def test_complete_posts_openai_shape_with_auth(monkeypatch):
    cap = {}
    body = json.dumps({"choices": [{"message": {"content": "  Photosynthesis makes sugar. "}}]}).encode()
    _patch_urlopen(monkeypatch, capture=cap, resp=_FakeResp(body=body))
    prov = CloudLLMProvider(_cfg(LLM_API_KEY="sk-test"))
    out = prov.complete([ChatMessage(role="user", content="what is photosynthesis?")])
    assert out.text == "Photosynthesis makes sugar."
    assert cap["url"] == "http://llm:8000/v1/chat/completions"
    # header keys are title-cased by urllib
    assert cap["headers"].get("Authorization") == "Bearer sk-test"
    assert cap["body"]["model"] == "edu-1"
    assert cap["body"]["stream"] is False


def test_complete_stream_yields_deltas(monkeypatch):
    cap = {}
    lines = [
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
        b'data: {"choices":[{"delta":{"content":" class"}}]}\n',
        b"data: [DONE]\n",
    ]
    _patch_urlopen(monkeypatch, capture=cap, resp=_FakeResp(lines=lines))
    prov = CloudLLMProvider(_cfg())
    chunks = list(prov.complete_stream([ChatMessage(role="user", content="hi")]))
    assert chunks == ["Hello", " class"]
    assert cap["body"]["stream"] is True


def test_llm_error_without_base_url():
    prov = CloudLLMProvider(load_config({"LLM_BASE_URL": ""}))
    with pytest.raises(LLMError):
        prov.complete([ChatMessage(role="user", content="x")])


def test_nemotron_defaults_to_nim():
    prov = NemotronLLMProvider(_cfg(NEMOTRON_API_KEY="nvapi-xyz"))
    info = prov.info()
    assert info.impl == "nemotron"
    assert info.endpoint == "https://integrate.api.nvidia.com/v1"
    assert prov._model.startswith("nvidia/")
    assert prov._api_key == "nvapi-xyz"


def test_factory_selects_nemotron_when_configured():
    fac = ProviderFactory(_cfg(NEMOTRON_API_KEY="nvapi-xyz"))
    assert isinstance(fac.llm(), NemotronLLMProvider)
    # Without a key it stays on the default local/cloud provider.
    fac2 = ProviderFactory(_cfg(DEPLOY_MODE="cloud"))
    assert not isinstance(fac2.llm(), NemotronLLMProvider)


def test_nemotron_configured_via_provider_switch():
    assert nemotron_configured(_cfg(LLM_PROVIDER="nemotron")) is True
    assert nemotron_configured(_cfg()) is False
