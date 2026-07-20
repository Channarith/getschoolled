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
    # Redirect the mobile version files too so a bump run never clobbers the real
    # apps/mobile/* files (write_mobile_version() only writes if the path exists).
    build_release.MOBILE_VERSION_FILE = tmp_path / "nope-mobile-version.ts"
    build_release.MOBILE_PACKAGE_JSON = tmp_path / "nope-mobile-package.json"
    build_release.MOBILE_APP_JSON = tmp_path / "nope-mobile-app.json"
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


def _many_pending(n: int) -> str:
    items = "\n".join(f"- pending item {i}" for i in range(n))
    return f"""CHANGELOG
=====

[unreleased]
{items}

[0.15.0] - 2026-06-23
- prior
"""


def test_auto_minor_when_over_threshold(monkeypatch, tmp_path):
    # >8 pending changes auto-promotes a PATCH to a MINOR (0.x.0).
    _setup(tmp_path, "0.15.0", _many_pending(9))
    monkeypatch.delenv("AOEP_MINOR_BUMP_THRESHOLD", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main([]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.16.0"


def test_no_auto_minor_at_or_below_threshold(monkeypatch, tmp_path):
    # Exactly 8 pending changes stays a PATCH (strictly greater than triggers).
    _setup(tmp_path, "0.15.0", _many_pending(8))
    monkeypatch.delenv("AOEP_MINOR_BUMP_THRESHOLD", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main([]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.15.1"


def test_threshold_env_override_disables_auto_minor(monkeypatch, tmp_path):
    _setup(tmp_path, "0.15.0", _many_pending(20))
    monkeypatch.setenv("AOEP_MINOR_BUMP_THRESHOLD", "0")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main([]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.15.1"


def test_threshold_env_override_cannot_weaken_policy(monkeypatch, tmp_path):
    # CI may inject a high threshold; clamp keeps >8 auto-minor intact.
    _setup(tmp_path, "0.15.0", _many_pending(9))
    monkeypatch.setenv("AOEP_MINOR_BUMP_THRESHOLD", "120")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main([]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.16.0"


def test_force_patch_overrides_auto_minor(monkeypatch, tmp_path):
    _setup(tmp_path, "0.15.0", _many_pending(20))
    monkeypatch.delenv("AOEP_MINOR_BUMP_THRESHOLD", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main(["--force-level", "patch"]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.15.1"


def test_bumps_from_base_branch_when_ahead(monkeypatch, tmp_path):
    # Branch VERSION is behind main (concurrent merge advanced main). The bump
    # must start from main's version, not the stale local one: 0.16.1 -> 0.16.2.
    _setup(tmp_path, "0.16.0", "CHANGELOG\n=====\n\n[unreleased]\n- x\n")
    monkeypatch.setattr(bump_pr, "base_branch_version", lambda *a, **k: ((0, 16, 1), "origin/main"))
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main(["--force-level", "patch"]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.16.2"


def test_uses_local_when_base_unavailable(monkeypatch, tmp_path):
    # Offline / base ref missing -> fall back to the local VERSION.
    _setup(tmp_path, "0.15.0", "CHANGELOG\n=====\n\n[unreleased]\n- x\n")
    monkeypatch.setattr(bump_pr, "base_branch_version", lambda *a, **k: (None, ""))
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main(["--force-level", "patch"]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.15.1"


def test_local_wins_when_ahead_of_base(monkeypatch, tmp_path):
    # If local is somehow ahead of main, keep bumping from local (never regress).
    _setup(tmp_path, "0.20.0", "CHANGELOG\n=====\n\n[unreleased]\n- x\n")
    monkeypatch.setattr(bump_pr, "base_branch_version", lambda *a, **k: ((0, 16, 1), "origin/main"))
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert bump_pr.main(["--force-level", "patch"]) == 0
    assert (tmp_path / "VERSION").read_text().strip() == "0.20.1"


def test_parse_version_helper():
    assert bump_pr._parse_version("0.16.1\n") == (0, 16, 1)
    assert bump_pr._parse_version("  1.2.3  ") == (1, 2, 3)
    assert bump_pr._parse_version("nonsense") is None
    assert bump_pr._parse_version("") is None


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
