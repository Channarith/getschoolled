"""Tests for the changelog-rolling logic (regression for the bare-header bug)."""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

build_release = importlib.import_module("build_release")


def _write(tmp_path, version, changelog):
    (tmp_path / "VERSION").write_text(version + "\n")
    (tmp_path / "CHANGELOG.txt").write_text(changelog)


def _point_module_at(tmp_path):
    build_release.REPO_ROOT = tmp_path
    build_release.VERSION_FILE = tmp_path / "VERSION"
    build_release.CHANGELOG_FILE = tmp_path / "CHANGELOG.txt"
    build_release.BUILD_INFO_FILE = tmp_path / "build-info.txt"
    build_release.WEB_VERSION_FILE = tmp_path / "nope-version.ts"
    build_release.WEB_PACKAGE_JSON = tmp_path / "nope-package.json"


BARE = """CHANGELOG
========

[unreleased]
- feat: did a thing
- fix: fixed a thing

[0.2.0] - 2026-06-17
- initial
"""


def test_bare_unreleased_header_is_recognized(monkeypatch, tmp_path):
    _write(tmp_path, "0.3.0", BARE)
    _point_module_at(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    rc = build_release.main([])
    assert rc == 0

    text = (tmp_path / "CHANGELOG.txt").read_text()
    # A fresh empty [unreleased] sits at the top.
    assert "[unreleased]\n- (no changes yet)" in text
    # The two items rolled into the new release (0.3.1), not lost.
    assert "[0.3.1] - " in text
    assert "feat: did a thing" in text
    assert text.index("[0.3.1]") < text.index("[0.2.0]")
    # No empty "no itemized changes" section was produced.
    assert "no itemized changes" not in text
    # VERSION advanced.
    assert (tmp_path / "VERSION").read_text().strip() == "0.3.1"


def test_dated_unreleased_header_still_works(monkeypatch, tmp_path):
    _write(tmp_path, "1.0.0", BARE.replace("[unreleased]", "[unreleased] - 2026-06-17"))
    _point_module_at(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert build_release.main([]) == 0
    text = (tmp_path / "CHANGELOG.txt").read_text()
    assert "[1.0.1] - " in text and "feat: did a thing" in text


def test_minor_bump_when_many_features(monkeypatch, tmp_path):
    items = "\n".join(f"- feat {i}" for i in range(9))
    _write(tmp_path, "0.3.0", f"CHANGELOG\n====\n\n[unreleased]\n{items}\n\n[0.2.0] - x\n- y\n")
    _point_module_at(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    build_release.main([])
    # >8 items -> minor bump.
    assert (tmp_path / "VERSION").read_text().strip() == "0.4.0"
