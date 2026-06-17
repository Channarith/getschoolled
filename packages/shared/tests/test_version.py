"""Version resolution tests (single source of truth)."""

import re
from pathlib import Path

import aoep_shared.version as version_mod
from aoep_shared import get_version

REPO_ROOT = Path(__file__).resolve().parents[3]
SEMVER = re.compile(r"^\d+\.\d+\.\d+")


def test_get_version_matches_version_file(monkeypatch):
    monkeypatch.delenv("AOEP_VERSION", raising=False)
    version_mod.get_version.cache_clear()
    expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert get_version() == expected
    assert SEMVER.match(get_version())


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("AOEP_VERSION", "9.9.9")
    version_mod.get_version.cache_clear()
    try:
        assert version_mod.get_version() == "9.9.9"
    finally:
        monkeypatch.delenv("AOEP_VERSION", raising=False)
        version_mod.get_version.cache_clear()


def test_version_is_cached(monkeypatch):
    monkeypatch.delenv("AOEP_VERSION", raising=False)
    version_mod.get_version.cache_clear()
    assert version_mod.get_version() is version_mod.get_version()


def test_service_health_reports_version(monkeypatch):
    monkeypatch.delenv("AOEP_VERSION", raising=False)
    version_mod.get_version.cache_clear()
    from fastapi.testclient import TestClient

    from aoep_shared.service import create_service

    app = create_service("version-probe")
    body = TestClient(app).get("/health").json()
    assert body["version"] == get_version()
    assert body["service"] == "version-probe"
