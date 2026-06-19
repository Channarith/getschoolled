"""test_endpoints_enabled gating."""

from aoep_shared import testsupport
from aoep_shared.config import AppConfig, DeployMode


def test_explicit_env_wins(monkeypatch):
    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "1")
    assert testsupport.test_endpoints_enabled() is True
    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "false")
    assert testsupport.test_endpoints_enabled() is False


def test_implicit_by_deploy_mode(monkeypatch):
    monkeypatch.delenv("ENABLE_TEST_ENDPOINTS", raising=False)
    assert testsupport.test_endpoints_enabled(AppConfig(deploy_mode=DeployMode.LOCAL)) is True
    assert testsupport.test_endpoints_enabled(AppConfig(deploy_mode=DeployMode.EDGE)) is True
    assert testsupport.test_endpoints_enabled(AppConfig(deploy_mode=DeployMode.CLOUD)) is False
