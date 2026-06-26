#!/usr/bin/env python3
"""Bump the release version for a pull request merging into main.

Every PR that lands on main must advance VERSION before merge. Run from the PR
branch after updating CHANGELOG.txt:

  python3 scripts/bump_pr_version.py

Release strategy (kept deliberately simple):
  * Routine PRs (bug fixes, cleanups, small changes) -> PATCH bump (0.9.y).
    This is the DEFAULT and what almost every PR should use.
  * A larger feature release -> MINOR bump (0.x.0) via --force-level minor.
  * A breaking/major release -> MAJOR bump (x.0.0) via --force-level major.

We intentionally do NOT auto-promote to a MINOR bump based on the size of the
[unreleased] changelog block. That block is rolled only by build_release.py at
formal release time, so per-PR it just keeps growing and would force a minor
bump on every PR -- making 0.x balloon far too quickly. Minor/major bumps are an
explicit decision, not a side effect of accumulated changelog text.

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
    else:
        # Default = PATCH. Routine PRs stay on 0.9.y; minor/major bumps are an
        # explicit --force-level decision (see module docstring for rationale).
        new_tuple = (current[0], current[1], current[2] + 1)

    new_version = ".".join(str(p) for p in new_tuple)
    sha = br.git_sha()
    components = br.discover_components()

    level = args.force_level or "patch (default)"
    print(f"current version:   {'.'.join(str(p) for p in current)}")
    print(f"bump level:        {level}")
    print(f"pending changelog: {pending} (informational only; does not force a bump)")
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
