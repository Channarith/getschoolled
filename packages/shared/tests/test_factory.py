"""Factory unit tests: local vs cloud selection by env (verification target)."""

import importlib

import pytest

from eduplatform_shared.config import DeployMode, get_settings
from eduplatform_shared.factory import ProviderFactory
from eduplatform_shared.providers import cloud as cloud_impl
from eduplatform_shared.providers import local as local_impl


def _factory(monkeypatch, **env) -> ProviderFactory:
    for key in (
        "DEPLOY_MODE",
        "LLM_MODE",
        "SPEECH_MODE",
        "VISION_MODE",
        "MEDIA_MODE",
        "OBJECT_STORE_MODE",
        "PAYMENT_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return ProviderFactory(get_settings(refresh=True))


def test_local_mode_selects_local_providers(monkeypatch):
    f = _factory(monkeypatch, DEPLOY_MODE="local")
    assert isinstance(f.llm(), local_impl.LocalLLMProvider)
    assert isinstance(f.speech(), local_impl.LocalSpeechProvider)
    assert isinstance(f.vision(), local_impl.LocalVisionProvider)
    assert isinstance(f.media(), local_impl.LocalMediaProvider)
    assert isinstance(f.object_store(), local_impl.LocalObjectStoreProvider)
    assert isinstance(f.payment(), local_impl.LocalPaymentProvider)


def test_cloud_mode_selects_cloud_providers(monkeypatch):
    f = _factory(monkeypatch, DEPLOY_MODE="cloud")
    assert isinstance(f.llm(), cloud_impl.CloudLLMProvider)
    assert isinstance(f.speech(), cloud_impl.CloudSpeechProvider)
    assert isinstance(f.vision(), cloud_impl.CloudVisionProvider)
    assert isinstance(f.media(), cloud_impl.CloudMediaProvider)
    assert isinstance(f.object_store(), cloud_impl.CloudObjectStoreProvider)
    assert isinstance(f.payment(), cloud_impl.CloudPaymentProvider)


def test_per_component_override_keeps_vision_local_in_cloud(monkeypatch):
    # Compliance lever: cloud everywhere, but biometrics stay local.
    f = _factory(monkeypatch, DEPLOY_MODE="cloud", VISION_MODE="local")
    assert isinstance(f.vision(), local_impl.LocalVisionProvider)
    assert isinstance(f.llm(), cloud_impl.CloudLLMProvider)


def test_default_mode_is_local(monkeypatch):
    f = _factory(monkeypatch)
    assert f.settings.deploy_mode is DeployMode.LOCAL
    assert isinstance(f.llm(), local_impl.LocalLLMProvider)


def test_blank_overrides_inherit_deploy_mode(monkeypatch):
    # config/local.env ships blank overrides; they must parse as "inherit".
    f = _factory(
        monkeypatch,
        DEPLOY_MODE="local",
        LLM_MODE="",
        VISION_MODE="",
        PAYMENT_MODE="",
    )
    assert isinstance(f.llm(), local_impl.LocalLLMProvider)
    assert isinstance(f.vision(), local_impl.LocalVisionProvider)
    assert isinstance(f.payment(), local_impl.LocalPaymentProvider)


def test_local_llm_grounds_answer_in_context(monkeypatch):
    f = _factory(monkeypatch, DEPLOY_MODE="local")
    llm = f.llm()
    out = llm.complete("QUESTION: what is gravity? CONTEXT: gravity pulls objects together")
    assert "gravity pulls objects" in out
    vecs = llm.embed(["hello world", "hello"])
    assert len(vecs) == 2 and len(vecs[0]) == 64
