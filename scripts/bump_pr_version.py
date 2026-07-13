#!/usr/bin/env python3
"""Bump the release version for a pull request merging into main.

Every PR that lands on main must advance VERSION before merge. Run from the PR
branch after updating CHANGELOG.txt:

  python3 scripts/bump_pr_version.py

Release strategy:
  * Routine PRs (bug fixes, cleanups, small changes) -> PATCH bump (0.x.y).
  * AUTO-MINOR: once more than MINOR_BUMP_THRESHOLD (default 8) features have
    been introduced or changed since the last release (counted from the pending
    changelog block), the next bump is promoted to a MINOR (0.x.0). This matches
    the project's "autobump to the next version when we have >8 features" rule.
  * --force-level {patch,minor,major} always overrides the automatic choice.

Tuning: set AOEP_MINOR_BUMP_THRESHOLD to change the >8 threshold (0 disables
auto-minor). build_release.py rolls the pending changelog block into a released
section at release time, which resets the counter so the next cycle starts at
PATCH again.

Updates VERSION, build-info.txt, apps/web/app/lib/version.ts, and
apps/web/package.json. Does NOT roll CHANGELOG.txt (dated PR bullets stay at top).

Use --check to print the computed version without writing files.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_release as br  # noqa: E402

# >N features/changes since the last release auto-promotes a PATCH to a MINOR.
DEFAULT_MINOR_BUMP_THRESHOLD = 8


def _minor_bump_threshold() -> int:
    raw = os.environ.get("AOEP_MINOR_BUMP_THRESHOLD", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return DEFAULT_MINOR_BUMP_THRESHOLD


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
    threshold = _minor_bump_threshold()

    # Resolve the bump level: explicit flag wins; otherwise auto-promote to MINOR
    # once >threshold features have accrued since the last release, else PATCH.
    if args.force_level:
        level = args.force_level
        auto = False
    elif threshold > 0 and pending > threshold:
        level = "minor"
        auto = True
    else:
        level = "patch"
        auto = False

    if level == "major":
        new_tuple = (current[0] + 1, 0, 0)
    elif level == "minor":
        new_tuple = (current[0], current[1] + 1, 0)
    else:
        new_tuple = (current[0], current[1], current[2] + 1)

    new_version = ".".join(str(p) for p in new_tuple)
    sha = br.git_sha()
    components = br.discover_components()

    reason = (f" (auto: {pending} > {threshold} pending changes)" if auto
              else " (forced)" if args.force_level
              else f" ({pending} pending <= {threshold} threshold)")
    print(f"current version:   {'.'.join(str(p) for p in current)}")
    print(f"bump level:        {level}{reason}")
    print(f"pending changelog: {pending}")
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
