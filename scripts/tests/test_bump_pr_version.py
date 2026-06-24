"""Tests for PR version bump helper."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

bump_pr = importlib.import_module("bump_pr_version")
build_release = importlib.import_module("build_release")


def _setup(tmp_path, version: str, changelog: str):
    (tmp_path / "VERSION").write_text(version + "\n")
    (tmp_path / "CHANGELOG.txt").write_text(changelog)
    build_release.REPO_ROOT = tmp_path
    build_release.VERSION_FILE = tmp_path / "VERSION"
    build_release.CHANGELOG_FILE = tmp_path / "CHANGELOG.txt"
    build_release.BUILD_INFO_FILE = tmp_path / "build-info.txt"
    build_release.WEB_VERSION_FILE = tmp_path / "nope-version.ts"
    build_release.WEB_PACKAGE_JSON = tmp_path / "nope-package.json"
    bump_pr.br = build_release


def test_pending_counts_dated_entries(monkeypatch, tmp_path):
    cl = """CHANGELOG
=====

- 2026-06-24 - one

[unreleased]
- pending item one
- pending item two

[0.3.0] - 2026-06-01
- old
"""
    _setup(tmp_path, "0.3.0", cl)
    assert bump_pr._pending_changelog_entries(cl) == 2


def test_bump_pr_version_patch(monkeypatch, tmp_path):
    cl = """CHANGELOG
=====

- 2026-06-24 - feature

[unreleased]
- (no changes yet)

[0.3.82] - 2026-06-23
- prior
"""
    _setup(tmp_path, "0.3.82", cl)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main([]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.3.83"


def test_build_release_refresh_only(monkeypatch, tmp_path):
    cl = """CHANGELOG
=====

[unreleased]
- (no changes yet)

[0.3.82] - 2026-06-23
- prior
"""
    _setup(tmp_path, "0.3.82", cl)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert build_release.main(["--refresh-only"]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.3.82"
    assert (tmp_path / "build-info.txt").exists()
