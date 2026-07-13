#!/usr/bin/env bash
# Configure repo-local git merge drivers so high-churn docs never block a merge
# (and the auto-push into main keeps flowing). Run once per clone:
#
#     ./scripts/setup-git.sh        # or:  make git-setup
#
# What this sets up (see .gitattributes for the per-path bindings):
#   - CHANGELOG.txt        -> union   (built-in; keeps BOTH sides' appended entries)
#   - build-info.txt       -> union   (built-in; generated file, keeps both)
#   - VERSION + version.ts -> maxver  (custom; keeps the HIGHER semantic version)
#   - README.md            -> theirs  (custom; accepts the INCOMING / theirs version)
#
# Notes:
#   * The `theirs` driver lives in repo-local git config (NOT committed), so each
#     clone / CI runner that performs a *local* merge must run this script first.
#   * GitHub's server-side merge (the "Merge" button / `gh pr merge`) honors the
#     built-in `union` driver but does NOT execute custom drivers (theirs/maxver).
#     For README or VERSION conflicts in PR auto-merge, do a local merge with
#     these drivers configured.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Custom "theirs" driver: take the other branch's (incoming) version wholesale.
# %A = current/ours result file (driver must write the final result here),
# %B = the other branch's (theirs/incoming) version.
git config merge.theirs.name "always take the incoming (theirs) version"
git config merge.theirs.driver 'cp -f -- "%B" "%A"'

# Custom "maxver" driver: keep the HIGHER semantic version so concurrent version
# bumps never block (VERSION + the generated version.ts files). See
# scripts/merge-version.sh.
git config merge.maxver.name "keep the higher semantic version"
git config merge.maxver.driver "$(git rev-parse --show-toplevel)/scripts/merge-version.sh %A %B"

# Reuse recorded conflict resolutions to make repeated merges smoother.
git config rerere.enabled true

echo "git merge drivers configured:"
echo "  CHANGELOG.txt        -> union  (keep both sides; via .gitattributes)"
echo "  build-info.txt       -> union  (generated; keep both; via .gitattributes)"
echo "  VERSION + version.ts -> maxver (keep higher version; via .gitattributes + merge.maxver)"
echo "  README.md            -> theirs (accept incoming; via .gitattributes + merge.theirs)"
