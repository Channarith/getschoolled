#!/usr/bin/env bash
# Record a production deployment on GitHub so the Deployments page matches reality.
# Usage: scripts/record_deployment.sh <git-sha> "<what was deployed>" [success|failure]
# Needs `gh` logged in. Safe to run after every manual docker build + kubectl rollout.
set -euo pipefail
sha="${1:?git sha}"; desc="${2:?description}"; state="${3:-success}"
repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
id="$(python3 -c 'import json,sys; print(json.dumps({"ref":sys.argv[1],"environment":"production","description":sys.argv[2][:140],"auto_merge":False,"required_contexts":[],"production_environment":True,"transient_environment":False}))' "$sha" "$desc" \
  | gh api "repos/$repo/deployments" --input - -q .id)"
gh api "repos/$repo/deployments/$id/statuses" -f state="$state" -f environment=production \
  -f environment_url="https://salareen.com" -f description="${desc:0:140}" >/dev/null
echo "recorded deployment $id ($state) for ${sha:0:8}"
