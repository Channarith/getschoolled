#!/usr/bin/env bash
# One health summary for all three machines, written to output/fleet/fleet-YYYY-MM-DD.txt (not committed).
# Run by hand or by launchd on the Mac (scripts/fleet/mac/com.salareen.fleet-daily.plist).
#
#   scripts/fleet/daily_report.sh            write the file and print its path
#   scripts/fleet/daily_report.sh --print    also print it
#
# Read-only: it runs fleet_status.sh (ssh, key login only) and nothing else. A machine that cannot be
# reached is reported as UNREACHABLE in the file, never retried in a loop.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
out_dir="$ROOT/output/fleet"
mkdir -p "$out_dir"
day="$(date +%F)"
file="$out_dir/fleet-$day.txt"
{
  echo "Salareen fleet health - $day $(date +%H:%M) ($(hostname -s))"
  echo "Roles: spark = LLM training + GPU translation + voice ingest; kalel = harvesting + GPU overflow; mac = coordination."
  echo "Plan and calendar: docs/ops-schedule.txt"
  echo
  "$ROOT/scripts/fleet_status.sh" 2>&1
  echo
  echo "Exit meaning: findings marked CRIT need action today, WARN this week, info is context."
} > "$file"
echo "$file"
[ "${1:-}" = "--print" ] && cat "$file"
# Keep a month of reports.
ls -1 "$out_dir"/fleet-*.txt 2>/dev/null | head -n -30 | xargs -I{} rm -f {} 2>/dev/null
exit 0
