#!/usr/bin/env python3
"""Bump the release version for a pull request merging into main.

Every PR that lands on main must advance VERSION before merge. Run from the PR
branch after updating CHANGELOG.txt:

  python3 scripts/bump_pr_version.py

Release strategy:
  * ALWAYS bump from the LATEST base: before computing the new version we fetch
    the base branch (default origin/main) and start from the HIGHER of the local
    VERSION and the base branch's VERSION. So even if this branch forked before a
    concurrent PR advanced main, the bump lands ABOVE main (e.g. main 0.16.1 +
    patch -> 0.16.2), never behind it. Use --no-fetch to skip the network fetch
    (still reads the local base ref if present).
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

Refreshes EVERY version file so they never drift: VERSION, build-info.txt,
apps/web/app/lib/version.ts + apps/web/package.json, and the mobile
src/version.ts + package.json + app.json. Does NOT roll CHANGELOG.txt (dated PR
bullets stay at top) — author the dated `- YYYY-MM-DD - vX.Y.Z - ...` line to
match the version this prints.

Use --check to print the computed version without writing files.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_release as br  # noqa: E402

# >N features/changes since the last release auto-promotes a PATCH to a MINOR.
DEFAULT_MINOR_BUMP_THRESHOLD = 120

Version = tuple[int, int, int]


def _minor_bump_threshold() -> int:
    raw = os.environ.get("AOEP_MINOR_BUMP_THRESHOLD", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return DEFAULT_MINOR_BUMP_THRESHOLD


def _parse_version(raw: str) -> Version | None:
    m = br.SEMVER_RE.match((raw or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _version_at_ref(ref: str) -> Version | None:
    """Read VERSION at a git ref (e.g. origin/main), or None if unavailable."""
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:VERSION"],
            cwd=str(br.REPO_ROOT), capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        return None
    return _parse_version(out)


def base_branch_version(base_ref: str, *, fetch: bool = True) -> tuple[Version | None, str]:
    """Latest VERSION on the base branch (fetches first so we never bump behind
    a concurrent merge). Returns (version, resolved_ref) or (None, "") if the
    base branch can't be resolved (e.g. offline first clone, or not a git repo)."""
    if fetch:
        try:
            subprocess.run(
                ["git", "fetch", "origin", base_ref, "--quiet"],
                cwd=str(br.REPO_ROOT), capture_output=True, text=True, timeout=60,
            )
        except (subprocess.SubprocessError, OSError):
            pass  # best-effort: fall back to whatever refs we already have
    for ref in (f"origin/{base_ref}", base_ref):
        v = _version_at_ref(ref)
        if v is not None:
            return v, ref
    return None, ""


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
    parser.add_argument(
        "--base-ref",
        default=os.environ.get("GITHUB_BASE_REF") or "main",
        help="Base branch to check for the latest version (default: main).",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip fetching the base branch (still reads a local base ref).",
    )
    args = parser.parse_args(argv)

    local = br.read_version()
    # Always start from the LATEST base: the higher of local VERSION and the base
    # branch's VERSION, so a bump lands above main even if this branch is behind.
    main_v, resolved_ref = base_branch_version(args.base_ref, fetch=not args.no_fetch)
    current = max(local, main_v) if main_v is not None else local
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
    ver = lambda v: ".".join(str(p) for p in v)  # noqa: E731
    if main_v is not None:
        base_note = f"{ver(main_v)} @ {resolved_ref}"
        if main_v > local:
            base_note += f" (ahead of local {ver(local)} — bumping from base)"
    else:
        base_note = f"unavailable (used local {ver(local)})"
    print(f"local version:     {ver(local)}")
    print(f"base branch:       {base_note}")
    print(f"bump from:         {ver(current)}")
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
