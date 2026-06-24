#!/usr/bin/env python3
"""Build-release helper for the auto-push-build pipeline.

This is the single piece of logic the CI workflow runs to turn "a build
happened" into "build changes committed back to the repo". It is intentionally
self-contained (stdlib only) so it runs identically locally and in CI, in both
local and cloud deploy modes.

Responsibilities:
  1. Bump VERSION (semver). Normally run via scripts/bump_pr_version.py in each
     PR before merge. This script (--refresh-only) can also roll the CHANGELOG
     [unreleased] section when invoked without --refresh-only. When MORE THAN 8
     features/changes have accumulated, bump the MINOR version (reset PATCH);
     otherwise bump PATCH.
  2. Roll the CHANGELOG [unreleased] section into a dated, versioned release
     section and start a fresh [unreleased] section.
  3. Write build-info.txt (version, git sha, UTC build time, components) so the
     repository always carries a record of the latest build.

Run `python3 scripts/build_release.py --help` for options. Use --check to print
what would happen without writing anything (used by tests / dry runs).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "VERSION"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.txt"
BUILD_INFO_FILE = REPO_ROOT / "build-info.txt"
WEB_VERSION_FILE = REPO_ROOT / "apps" / "web" / "app" / "lib" / "version.ts"
WEB_PACKAGE_JSON = REPO_ROOT / "apps" / "web" / "package.json"

# More than this many unreleased entries triggers a MINOR bump instead of PATCH.
FEATURE_BUMP_THRESHOLD = 8

SEMVER_RE = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$")
# Matches the unreleased header in both bare ("[unreleased]") and dated
# ("[unreleased] - 2026-06-17") forms. The bare form previously slipped through
# and broke changelog rolling, so accept either.
UNRELEASED_HEADER_RE = re.compile(r"^\[unreleased\]\s*(?:-.*)?$", re.IGNORECASE)


def read_version() -> tuple[int, int, int]:
    raw = VERSION_FILE.read_text(encoding="utf-8").strip()
    m = SEMVER_RE.match(raw)
    if not m:
        raise SystemExit(f"VERSION file is not valid semver: {raw!r}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def parse_changelog() -> tuple[list[str], list[str], list[str]]:
    """Split CHANGELOG into (header_lines, unreleased_entry_lines, rest_lines).

    header_lines: everything up to and including the [unreleased] header line.
    unreleased_entry_lines: the body lines belonging to the [unreleased] block.
    rest_lines: the first previous-release header onward (may be empty).
    """
    return parse_changelog_from_text(CHANGELOG_FILE.read_text(encoding="utf-8"))


def parse_changelog_from_text(text: str) -> tuple[list[str], list[str], list[str]]:
    """Parse CHANGELOG text into header, unreleased body, and prior releases."""
    lines = text.splitlines()
    header: list[str] = []
    unreleased: list[str] = []
    rest: list[str] = []

    idx = 0
    # Collect file preamble until the [unreleased] header.
    while idx < len(lines):
        header.append(lines[idx])
        if UNRELEASED_HEADER_RE.match(lines[idx].strip()):
            idx += 1
            break
        idx += 1

    # Collect unreleased body until the next bracketed release header.
    while idx < len(lines):
        line = lines[idx]
        if line.strip().startswith("[") and not UNRELEASED_HEADER_RE.match(line.strip()):
            break
        unreleased.append(line)
        idx += 1

    rest = lines[idx:]
    return header, unreleased, rest


def count_feature_entries(unreleased_lines: list[str]) -> int:
    return sum(1 for ln in unreleased_lines if ln.lstrip().startswith("- "))


def bump(version: tuple[int, int, int], feature_count: int) -> tuple[int, int, int]:
    major, minor, patch = version
    if feature_count > FEATURE_BUMP_THRESHOLD:
        return major, minor + 1, 0
    return major, minor, patch + 1


def git_sha() -> str:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha[:12]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def discover_components() -> list[str]:
    """List buildable components present in the repo (graceful if absent)."""
    components: list[str] = []
    web = REPO_ROOT / "apps" / "web"
    if (web / "package.json").exists():
        components.append("apps/web")
    for parent in ("apps", "services"):
        base = REPO_ROOT / parent
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.name == "web":
                continue
            if (child / "requirements.txt").exists() or (child / "pyproject.toml").exists():
                components.append(f"{parent}/{child.name}")
    shared = REPO_ROOT / "packages" / "shared"
    if (shared / "pyproject.toml").exists():
        components.append("packages/shared")
    return components


def render_build_info(version_str: str, sha: str, components: list[str]) -> str:
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deploy_mode = os.environ.get("DEPLOY_MODE", "unset")
    comp_text = ", ".join(components) if components else "(none discovered yet)"
    return (
        "BUILD INFO - Agentic Online Education Platform\n"
        "==============================================\n"
        "Auto-generated by scripts/build_release.py on each build. Do not edit by hand.\n"
        "\n"
        f"version:     {version_str}\n"
        f"git_sha:     {sha}\n"
        f"built_utc:   {now}\n"
        f"deploy_mode: {deploy_mode}\n"
        f"components:  {comp_text}\n"
    )


def write_changelog(
    header: list[str],
    unreleased: list[str],
    rest: list[str],
    new_version: str,
) -> None:
    today = _dt.date.today().isoformat()
    # Replace the [unreleased] header line (last line of header) with a fresh
    # empty [unreleased] block, then the newly released, dated section.
    preamble = header[:-1]

    new_lines: list[str] = []
    new_lines.extend(preamble)
    new_lines.append("[unreleased]")
    new_lines.append("- (no changes yet)")
    new_lines.append("")
    new_lines.append(f"[{new_version}] - {today}")
    # Carry over the previous unreleased entries (strip leading/trailing blanks).
    body = [ln for ln in unreleased]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    if not body:
        body = ["- release build (no itemized changes)"]
    new_lines.extend(body)
    new_lines.append("")
    new_lines.extend(rest)

    text = "\n".join(new_lines).rstrip("\n") + "\n"
    CHANGELOG_FILE.write_text(text, encoding="utf-8")


def write_web_version(new_version: str) -> None:
    """Keep the web app's displayed version in sync with VERSION.

    Updates the ``GENERATED_VERSION`` constant in app/lib/version.ts and the
    ``version`` field in package.json. No-ops gracefully if the web app is
    absent (e.g. before it is scaffolded).
    """
    if WEB_VERSION_FILE.exists():
        text = WEB_VERSION_FILE.read_text(encoding="utf-8")
        text = re.sub(
            r'const GENERATED_VERSION = "[^"]*";',
            f'const GENERATED_VERSION = "{new_version}";',
            text,
        )
        WEB_VERSION_FILE.write_text(text, encoding="utf-8")
    if WEB_PACKAGE_JSON.exists():
        text = WEB_PACKAGE_JSON.read_text(encoding="utf-8")
        text = re.sub(
            r'("version"\s*:\s*")[^"]*(")',
            rf'\g<1>{new_version}\g<2>',
            text,
            count=1,
        )
        WEB_PACKAGE_JSON.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run: print the computed version/build info, write nothing.",
    )
    parser.add_argument(
        "--force-level",
        choices=["patch", "minor", "major"],
        help="Override the automatic bump level.",
    )
    parser.add_argument(
        "--refresh-only",
        action="store_true",
        help="Do not bump VERSION; refresh build-info.txt and sync web version files.",
    )
    args = parser.parse_args(argv)

    current = read_version()
    header, unreleased, rest = parse_changelog()
    feature_count = count_feature_entries(unreleased)

    if args.refresh_only:
        new_version_tuple = current
    elif args.force_level == "major":
        new_version_tuple = (current[0] + 1, 0, 0)
    elif args.force_level == "minor":
        new_version_tuple = (current[0], current[1] + 1, 0)
    elif args.force_level == "patch":
        new_version_tuple = (current[0], current[1], current[2] + 1)
    else:
        new_version_tuple = bump(current, feature_count)

    new_version = ".".join(str(p) for p in new_version_tuple)
    sha = git_sha()
    components = discover_components()

    print(f"current version:  {'.'.join(str(p) for p in current)}")
    if args.refresh_only:
        print("mode:             refresh-only (no VERSION bump)")
    else:
        print(f"unreleased items:  {feature_count} (threshold > {FEATURE_BUMP_THRESHOLD})")
    print(f"new version:       {new_version}")
    print(f"git sha:           {sha}")
    print(f"components:         {', '.join(components) if components else '(none)'}")

    if args.check:
        print("--check set: no files written.")
        return 0

    if not args.refresh_only:
        VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")
        write_changelog(header, unreleased, rest, new_version)
    BUILD_INFO_FILE.write_text(
        render_build_info(new_version, sha, components), encoding="utf-8"
    )
    write_web_version(new_version)

    if args.refresh_only:
        print("refreshed build-info.txt and web version (VERSION unchanged)")
    else:
        print("wrote VERSION, build-info.txt, CHANGELOG.txt, web version")
    return 0


if __name__ == "__main__":
    sys.exit(main())
