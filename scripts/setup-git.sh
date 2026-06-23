#!/usr/bin/env bash
# Configure repo-local git merge drivers so high-churn docs never block a merge
# (and the auto-push into main keeps flowing). Run once per clone:
#
#     ./scripts/setup-git.sh        # or:  make git-setup
#
# What this sets up (see .gitattributes for the per-path bindings):
#   - CHANGELOG.txt -> union   (built-in; keeps BOTH sides' appended entries)
#   - README.md     -> theirs  (custom; accepts the INCOMING / theirs version)
#
# Notes:
#   * The `theirs` driver lives in repo-local git config (NOT committed), so each
#     clone / CI runner that performs a *local* merge must run this script first.
#   * GitHub's server-side merge (the "Merge" button / `gh pr merge`) honors the
#     built-in `union` driver but does NOT execute custom drivers. For README
#     conflicts in PR auto-merge, do a local merge with this driver configured.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Custom "theirs" driver: take the other branch's (incoming) version wholesale.
# %A = current/ours result file (driver must write the final result here),
# %B = the other branch's (theirs/incoming) version.
git config merge.theirs.name "always take the incoming (theirs) version"
git config merge.theirs.driver 'cp -f -- "%B" "%A"'

# Reuse recorded conflict resolutions to make repeated merges smoother.
git config rerere.enabled true

echo "git merge drivers configured:"
echo "  CHANGELOG.txt -> union  (keep both sides; via .gitattributes)"
echo "  README.md     -> theirs (accept incoming; via .gitattributes + merge.theirs)"
