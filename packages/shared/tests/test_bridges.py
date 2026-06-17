"""Phases 7-9 - bridge interface/registry/readiness tests."""

import pytest

from aoep_shared.bridges import (
    BridgePlatform,
    BridgeUnavailable,
    capabilities,
    get_bridge,
    is_ready,
    missing_credentials,
)


def test_registry_covers_all_platforms():
    for p in BridgePlatform:
        caps = capabilities(p)
        assert caps.platform is p
        assert caps.required_credentials


def test_teams_is_dotnet():
    assert capabilities(BridgePlatform.TEAMS).runtime == "dotnet"
    assert capabilities(BridgePlatform.ZOOM).runtime == "python"


def test_missing_credentials_and_readiness():
    env = {}
    assert missing_credentials(BridgePlatform.ZOOM, env) == ["ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"]
    assert is_ready(BridgePlatform.ZOOM, env) is False
    full = {"ZOOM_SDK_KEY": "k", "ZOOM_SDK_SECRET": "s"}
    assert missing_credentials(BridgePlatform.ZOOM, full) == []
    assert is_ready(BridgePlatform.ZOOM, full) is True


def test_bridge_connect_without_credentials_raises(monkeypatch):
    for var in ("ZOOM_SDK_KEY", "ZOOM_SDK_SECRET"):
        monkeypatch.delenv(var, raising=False)
    bridge = get_bridge(BridgePlatform.ZOOM)
    with pytest.raises(BridgeUnavailable) as exc:
        bridge.connect("https://zoom.us/j/123", livekit_room="class-1")
    assert "credentials" in str(exc.value)


def test_bridge_connect_with_credentials_needs_sdk(monkeypatch):
    monkeypatch.setenv("ZOOM_SDK_KEY", "k")
    monkeypatch.setenv("ZOOM_SDK_SECRET", "s")
    bridge = get_bridge(BridgePlatform.ZOOM)
    with pytest.raises(BridgeUnavailable) as exc:
        bridge.connect("https://zoom.us/j/123", livekit_room="class-1")
    assert "SDK" in str(exc.value)
