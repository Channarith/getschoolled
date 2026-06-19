"""version.build_info() metadata."""

from aoep_shared.version import API_VERSION, build_info, get_version


def test_build_info_has_version_and_api_version():
    info = build_info()
    assert info["version"] == get_version()
    assert info["api_version"] == API_VERSION
    assert "git_sha" in info and "build_time" in info


def test_git_sha_and_build_time_from_env(monkeypatch):
    monkeypatch.setenv("AOEP_GIT_SHA", "abc1234")
    monkeypatch.setenv("AOEP_BUILD_TIME", "2026-06-19T00:00:00Z")
    info = build_info()
    assert info["git_sha"] == "abc1234"
    assert info["build_time"] == "2026-06-19T00:00:00Z"
