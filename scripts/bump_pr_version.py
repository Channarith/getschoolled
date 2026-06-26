#!/usr/bin/env python3
"""Bump the release version for a pull request merging into main.

Every PR that lands on main must advance VERSION before merge. Run from the PR
branch after updating CHANGELOG.txt:

  python3 scripts/bump_pr_version.py

Default: PATCH bump. If more than 8 pending changelog entries have accumulated
since the last versioned release section, bumps MINOR instead (resets PATCH).

Updates VERSION, build-info.txt, apps/web/app/lib/version.ts, and
apps/web/package.json. Does NOT roll CHANGELOG.txt (dated PR bullets stay at top).

Use --check to print the computed version without writing files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_release as br  # noqa: E402

FEATURE_BUMP_THRESHOLD = br.FEATURE_BUMP_THRESHOLD


def _pending_changelog_entries(text: str) -> int:
    """Count items in the [unreleased] block (same rule as build_release.py)."""
    _, unreleased, _ = br.parse_changelog_from_text(text)
    return br.count_feature_entries(unreleased)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry run: print the computed version, write nothing.",
    )
    parser.add_argument(
        "--force-level",
        choices=["patch", "minor", "major"],
        help="Override automatic bump level.",
    )
    args = parser.parse_args(argv)

    current = br.read_version()
    changelog_text = br.CHANGELOG_FILE.read_text(encoding="utf-8")
    pending = _pending_changelog_entries(changelog_text)

    if args.force_level == "major":
        new_tuple = (current[0] + 1, 0, 0)
    elif args.force_level == "minor":
        new_tuple = (current[0], current[1] + 1, 0)
    elif args.force_level == "patch":
        new_tuple = (current[0], current[1], current[2] + 1)
    else:
        new_tuple = br.bump(current, pending)

    new_version = ".".join(str(p) for p in new_tuple)
    sha = br.git_sha()
    components = br.discover_components()

    print(f"current version:   {'.'.join(str(p) for p in current)}")
    print(f"pending changelog: {pending} (minor threshold > {FEATURE_BUMP_THRESHOLD})")
    print(f"new version:       {new_version}")

    if args.check:
        print("--check set: no files written.")
        return 0

    br.VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")
    br.BUILD_INFO_FILE.write_text(
        br.render_build_info(new_version, sha, components), encoding="utf-8"
    )
    br.write_web_version(new_version)
    br.write_mobile_version(new_version)
    print("wrote VERSION, build-info.txt, web and mobile version files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
