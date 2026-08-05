#!/usr/bin/env bash
# Lift labs/theodore-webcam out of the monorepo into its own private repo,
# keeping only this directory's history.
#
#   ./scripts/split_subrepo.sh git@github.com:<org>/theodore-webcam.git [branch]
#
# Nothing in the monorepo imports this lab, so no other change is required
# after the split.
set -euo pipefail

REMOTE="${1:-}"
BRANCH="${2:-main}"
PREFIX="labs/theodore-webcam"

if [ -z "$REMOTE" ]; then
  echo "usage: $0 <git-remote-url> [branch]" >&2
  exit 2
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [ ! -d "$PREFIX" ]; then
  echo "error: $PREFIX not found from $REPO_ROOT" >&2
  exit 1
fi

SPLIT_BRANCH="subrepo-split-$(date +%s)"
echo "==> splitting $PREFIX history into $SPLIT_BRANCH"
git subtree split --prefix="$PREFIX" -b "$SPLIT_BRANCH"

echo "==> pushing $SPLIT_BRANCH to $REMOTE as $BRANCH"
git push "$REMOTE" "$SPLIT_BRANCH:refs/heads/$BRANCH"

echo "==> cleaning up local split branch"
git branch -D "$SPLIT_BRANCH"

cat <<EOF

Done. Clone the private repo with:

  git clone $REMOTE
  cd \$(basename "$REMOTE" .git)
  python3 -m venv .venv && . .venv/bin/activate
  pip install -e '.[test]'
  make test && make run

Remember to set the new repository to Private in the host's settings.
EOF
