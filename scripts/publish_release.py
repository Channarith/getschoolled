#!/usr/bin/env python3
"""
publish_release.py - create any missing GitHub Releases from the local repo.

Replaces the deleted .github/workflows/release.yml. Scans the VERSION file at
every commit on `origin/main`, finds versions that don't yet have a GitHub
Release, pulls the matching CHANGELOG.txt entry as release notes, and creates
the Release via `gh release create`.

Idempotent: a version that already has a Release on GitHub is skipped. Safe to
run after every merge, every deploy, or on a cron. The script never pushes
tags itself - the `gh release create` call creates the tag server-side at the
commit sha where the VERSION file first held that value.

Usage:
  python3 scripts/publish_release.py                 # create all missing
  python3 scripts/publish_release.py --dry-run       # show what would be created
  python3 scripts/publish_release.py --limit 5       # only the N most recent
  python3 scripts/publish_release.py --repo A/B      # override repo (default:
                                                     # `origin` remote)

Prereqs:
  - `gh` CLI logged in (`gh auth status`)
  - Up-to-date `origin/main` (the script runs `git fetch origin main --quiet`)

Why this exists:
  GitHub Actions is disabled on this repo (billing / spend-limit policy). The
  Release workflow was the one piece of CI we still relied on. This script is
  the manual replacement - run it from a cron, from `scripts/deploy_vke.sh`,
  or by hand after a merge.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Optional


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.txt"
VERSION_PATH_IN_REPO = "VERSION"
# Match the "- YYYY-MM-DD - vX.Y.Z - ..." bullet convention. The capture group
# yanks the full entry up to (but not including) the next bullet-or-section.
CHANGELOG_ENTRY_RE = re.compile(
    r"^- \d{4}-\d{2}-\d{2} - v(?P<ver>\d+\.\d+\.\d+) - ",
    re.MULTILINE,
)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """subprocess.run with check=True and text=True by default."""
    kw.setdefault("check", True)
    kw.setdefault("text", True)
    kw.setdefault("capture_output", True)
    return subprocess.run(cmd, **kw)


def detect_repo() -> str:
    """Return 'owner/name' from the `origin` remote URL."""
    url = run(["git", "-C", str(REPO_ROOT), "remote", "get-url", "origin"]).stdout.strip()
    # Handle both https://github.com/A/B(.git) and git@github.com:A/B(.git)
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", url)
    if not m:
        raise SystemExit(f"Cannot parse 'owner/name' from origin URL: {url}")
    return m.group(1)


def existing_release_tags(repo: str) -> set[str]:
    """List tag names of releases that already exist on GitHub."""
    out = run(
        ["gh", "release", "list", "--repo", repo, "--limit", "1000",
         "--json", "tagName"],
    ).stdout
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise SystemExit(f"Unexpected gh output:\n{out}")
    return {item["tagName"] for item in data}


def versions_on_main() -> list[tuple[str, str]]:
    """Return [(sha, version), ...] in main-newest-first order. One entry per
    DISTINCT VERSION value - the sha is the FIRST commit (newest-first order,
    so the LAST commit chronologically) at which that version appeared, which
    is where we want the tag to land."""
    run(["git", "-C", str(REPO_ROOT), "fetch", "origin", "main", "--quiet"])
    log = run([
        "git", "-C", str(REPO_ROOT), "log", "origin/main",
        "--format=%H", "--", VERSION_PATH_IN_REPO,
    ]).stdout.splitlines()
    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for sha in log:
        try:
            raw = run([
                "git", "-C", str(REPO_ROOT), "show", f"{sha}:{VERSION_PATH_IN_REPO}",
            ]).stdout
        except subprocess.CalledProcessError:
            continue
        ver = raw.strip()
        if not ver or ver in seen:
            continue
        seen.add(ver)
        rows.append((sha, ver))
    return rows


def changelog_entry(version: str) -> Optional[str]:
    """Pull the `- YYYY-MM-DD - vX.Y.Z - ...` bullet for `version` from
    CHANGELOG.txt. Returns the full text of just that one bullet (which may
    span multiple lines because entries don't wrap)."""
    text = CHANGELOG.read_text(encoding="utf-8")
    start = None
    for m in CHANGELOG_ENTRY_RE.finditer(text):
        if m.group("ver") == version:
            start = m.start()
            break
    if start is None:
        return None
    # End = start of the NEXT entry OR start of the next bracketed section.
    rest = text[start + 1 :]
    end_rel = len(rest)
    for m in CHANGELOG_ENTRY_RE.finditer(rest):
        end_rel = m.start()
        break
    section = re.search(r"^\[", rest, flags=re.MULTILINE)
    if section and section.start() < end_rel:
        end_rel = section.start()
    return text[start : start + 1 + end_rel].rstrip() + "\n"


def create_release(repo: str, version: str, sha: str, notes: str, dry: bool) -> None:
    tag = f"v{version}"
    print(f"==> create {tag}  target={sha[:7]}  notes={len(notes)} chars")
    if dry:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(notes)
        notes_path = f.name
    try:
        run([
            "gh", "release", "create", tag,
            "--repo", repo,
            "--title", tag,
            "--notes-file", notes_path,
            "--target", sha,
        ])
        print(f"   https://github.com/{repo}/releases/tag/{tag}")
    finally:
        os.unlink(notes_path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--repo", default=None,
                    help="owner/name (default: parsed from `origin` remote)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be created, don't call `gh release create`")
    ap.add_argument("--limit", type=int, default=0,
                    help="process at most N missing versions (0 = all)")
    ap.add_argument("--all", action="store_true",
                    help="also backfill versions older than the newest "
                         "existing release (default: only backfill versions "
                         "newer than the latest release on GitHub, so stale "
                         "legacy gaps are left alone)")
    args = ap.parse_args()

    repo = args.repo or detect_repo()
    print(f"Repo:  {repo}")
    print(f"Scan:  origin/main VERSION history")

    existing = existing_release_tags(repo)
    print(f"       {len(existing)} releases already on GitHub")

    # Highest existing release version as a semver tuple, so we can skip
    # legacy gaps unless --all is passed. Treat non-semver tags as 0.0.0.
    def _parse(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (0, 0, 0)
    highest = max((_parse(t.lstrip("v")) for t in existing), default=(0, 0, 0))

    missing: list[tuple[str, str]] = []
    for sha, ver in versions_on_main():
        if f"v{ver}" in existing:
            continue
        if not args.all and _parse(ver) < highest:
            # Legacy gap - leave it alone unless the operator opted in.
            continue
        missing.append((sha, ver))

    # Chronological order (oldest first) so GitHub's "Latest" lands on the
    # newest version even if we were offline for a long stretch.
    missing.reverse()

    if args.limit:
        missing = missing[-args.limit :]

    if not missing:
        print("       all versions have releases - nothing to do.")
        return 0

    print(f"       {len(missing)} missing: " + ", ".join(f"v{v}" for _, v in missing))

    for sha, ver in missing:
        notes = changelog_entry(ver)
        if notes is None:
            notes = f"Release v{ver}. See CHANGELOG.txt for details.\n"
        create_release(repo, ver, sha, notes, args.dry_run)

    return 0


if __name__ == "__main__":
    sys.exit(main())
