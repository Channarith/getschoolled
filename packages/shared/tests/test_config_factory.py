"""Factory unit test: local vs cloud selection by env (phase0 target)."""

from aoep_shared.config import DeployMode, load_config
from aoep_shared.factory import build_factory
from aoep_shared.providers.llm import CloudLLMProvider, LocalLLMProvider
from aoep_shared.providers.media import CloudMediaProvider, LocalMediaProvider
from aoep_shared.providers.payment import (
    SandboxPaymentProvider,
    StripePaymentProvider,
)


def test_default_is_local_everywhere():
    cfg = load_config(env={})
    assert cfg.deploy_mode is DeployMode.LOCAL
    for component in ("llm", "speech", "vision", "media", "object_store", "payment"):
        assert cfg.is_local(component)


def test_deploy_mode_cloud_flips_all_components():
    cfg = load_config(env={"DEPLOY_MODE": "cloud"})
    assert cfg.deploy_mode is DeployMode.CLOUD
    factory = build_factory(cfg)
    assert isinstance(factory.llm(), CloudLLMProvider)
    assert isinstance(factory.media(), CloudMediaProvider)
    assert isinstance(factory.payment(), StripePaymentProvider)


def test_per_component_override_keeps_biometrics_local():
    # Cloud everything, but pin vision local (compliance boundary).
    cfg = load_config(env={"DEPLOY_MODE": "cloud", "VISION_MODE": "local"})
    assert cfg.is_cloud("llm")
    assert cfg.is_local("vision")
    factory = build_factory(cfg)
    assert isinstance(factory.llm(), CloudLLMProvider)
    assert factory.vision().info().mode == "local"


def test_local_mode_selects_local_impls():
    cfg = load_config(env={"DEPLOY_MODE": "local"})
    factory = build_factory(cfg)
    assert isinstance(factory.llm(), LocalLLMProvider)
    assert isinstance(factory.media(), LocalMediaProvider)
    assert isinstance(factory.payment(), SandboxPaymentProvider)


def test_factory_caches_instances():
    factory = build_factory(load_config(env={}))
    assert factory.llm() is factory.llm()


def test_component_summary_reports_mode_and_impl():
    factory = build_factory(load_config(env={"DEPLOY_MODE": "cloud"}))
    summary = factory.component_summary()
    assert summary["llm"].startswith("cloud:")
    assert summary["payment"] == "cloud:stripe"


def test_invalid_mode_raises():
    import pytest

    with pytest.raises(ValueError):
        load_config(env={"DEPLOY_MODE": "hybrid"})
