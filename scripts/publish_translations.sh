#!/usr/bin/env bash
# Publish validated course translations (Spark + kalel) to the private object-store prefix.
#   scripts/publish_translations.sh              pull + build + DRY RUN (nothing is uploaded)
#   scripts/publish_translations.sh --yes        also upload (private objects, manifest last)
#   scripts/publish_translations.sh --no-pull    reuse what is already in ~/translations-staging
#   scripts/publish_translations.sh --prune      with --yes: delete objects that left the manifest
#   scripts/publish_translations.sh --allow-shrink   needed to publish a set that drops more than half of what is live
#   scripts/publish_translations.sh withdraw --lang km [--course ID] [--yes] [--prune]
#   scripts/publish_translations.sh status
# Read-only on the machines (rsync pull over key-based ssh). See docs/translations-delivery.txt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PUBLISH_PY:-$ROOT/.venv/bin/python}"; [ -x "$PY" ] || PY=python3
run() { env PYTHONPATH="$ROOT/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}" "$PY" "$ROOT/scripts/publish_translations.py" "$@"; }
case "${1:-}" in withdraw|status) cmd="$1"; shift; run "$cmd" "$@"; exit $? ;; esac
yes=""; prune=""; shrink=""; pull=1
for arg in "$@"; do case "$arg" in --yes) yes="--yes" ;; --prune) prune="--prune" ;; --allow-shrink) shrink="--allow-shrink" ;; --no-pull) pull=0 ;; *) echo "unknown option: $arg" >&2; exit 64 ;; esac; done
[ "$pull" = 1 ] && run pull
run build
run upload $yes $prune $shrink
