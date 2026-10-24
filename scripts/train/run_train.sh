#!/usr/bin/env bash
# run_train.sh - one scheduled pass of the merge train (called by launchd or a systemd timer).
#
#   TRAIN_APPLY=1       actually merge/deploy (default: dry run, which only writes the summary)
#   TRAIN_WINDOW=08-23  only act between these local hours (default 08-23); outside it the pass is a dry run
#   TRAIN_MAX_MERGES=1
#
# Safety: honours scripts/train/PAUSE, holds one lock, writes output/train/run.log and output/train/latest-summary.txt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
# launchd and systemd start with a minimal PATH: add the usual tool locations.
export PATH="/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:${PATH}"
mkdir -p output/train

START="${TRAIN_WINDOW:-08-23}"
FIRST="${START%-*}"; LAST="${START#*-}"
HOUR="$(date +%H)"
APPLY="${TRAIN_APPLY:-0}"
if [ "${APPLY}" = "1" ] && { [ "$((10#${HOUR}))" -lt "$((10#${FIRST}))" ] || [ "$((10#${HOUR}))" -ge "$((10#${LAST}))" ]; }; then
  echo "$(date '+%F %T') outside window ${START}: dry run only" >> output/train/run.log
  APPLY=0
fi

ARGS=(--max-merges "${TRAIN_MAX_MERGES:-1}")
[ "${APPLY}" = "1" ] && ARGS+=(--apply)

{
  echo "=== $(date '+%F %T') merge train (apply=${APPLY}) ==="
  # caffeinate keeps a Mac awake for the duration of this pass only (it cannot wake a sleeping Mac).
  if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -i python3 scripts/merge_train.py "${ARGS[@]}" || echo "exit $?"
  else
    python3 scripts/merge_train.py "${ARGS[@]}" || echo "exit $?"
  fi
} >> output/train/run.log 2>&1

# keep the log from growing forever
if [ "$(wc -c < output/train/run.log)" -gt 5000000 ]; then
  tail -c 1000000 output/train/run.log > output/train/run.log.tmp && mv output/train/run.log.tmp output/train/run.log
fi
