"""Edge / local-first profile conformance tests (Phase 13)."""

from aoep_shared.config import AppConfig, DeployMode, load_config
from aoep_shared.edge import assert_offline, edge_config, edge_report, offline_violations
from aoep_shared.factory import ProviderFactory


def test_edge_mode_parsed_from_env():
    cfg = load_config({"DEPLOY_MODE": "edge"})
    assert cfg.deploy_mode is DeployMode.EDGE
    assert cfg.is_edge is True


def test_edge_selects_local_providers_everywhere():
    fac = ProviderFactory(edge_config())
    report = edge_report(fac)
    assert all(v.startswith("local") for v in report.values()), report
    assert offline_violations(fac) == []
    assert_offline(fac)  # does not raise


def test_edge_llm_is_local_not_cloud():
    fac = ProviderFactory(edge_config())
    assert fac.llm().info().mode == "local"


def test_cloud_profile_violates_offline():
    fac = ProviderFactory(AppConfig(deploy_mode=DeployMode.CLOUD))
    # At least one capability is cloud-backed -> not offline.
    assert offline_violations(fac)


def test_is_local_true_for_edge_components():
    cfg = edge_config()
    assert cfg.is_local("llm") is True
    assert cfg.is_cloud("llm") is False
