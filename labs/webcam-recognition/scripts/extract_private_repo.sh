#!/usr/bin/env bash
# Extract labs/webcam-recognition into a standalone private GitHub repository.
#
# Usage:
#   ./scripts/extract_private_repo.sh [owner/repo-name]
#
# Example:
#   ./scripts/extract_private_repo.sh Channarith/webcam-recognition-lab
#
# Requires: git, gh (authenticated), network access to github.com.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_NAME="${1:-Channarith/webcam-recognition-lab}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Packaging $ROOT -> private repo $REPO_NAME"
mkdir -p "$TMP/repo"
# Copy lab tree (exclude caches).
rsync -a --exclude '__pycache__' --exclude '.pytest_cache' --exclude '*.egg-info' \
  --exclude '.venv' --exclude '.env' \
  "$ROOT/" "$TMP/repo/"

cd "$TMP/repo"
git init -b main
git add -A
git -c user.email="webcam-lab@salareen.local" -c user.name="Webcam Lab" \
  commit -m "Initial private webcam recognition lab (silhouette, absence, xAI voice)."

if gh repo view "$REPO_NAME" >/dev/null 2>&1; then
  echo "Remote $REPO_NAME already exists — pushing main."
else
  gh repo create "$REPO_NAME" --private --source=. --remote=origin --push
  echo "Created private repo: https://github.com/$REPO_NAME"
  exit 0
fi

git remote add origin "https://github.com/${REPO_NAME}.git" 2>/dev/null || true
git push -u origin main
echo "Pushed to https://github.com/$REPO_NAME"
