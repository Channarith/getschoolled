#!/usr/bin/env bash
# Git merge driver: resolve a version-bearing file by keeping the HIGHER semver.
#
# Bound to VERSION + the generated version.ts files in .gitattributes (merge=maxver)
# and wired by scripts/setup-git.sh. When two branches bump the version to
# different values, this never conflicts — it keeps whichever side has the higher
# semantic version (so `main` only ever moves forward). These files carry nothing
# but the version, so taking the higher side wholesale is safe.
#
# Args (from git):  %A = ours (also the RESULT file)   %B = theirs
# Exit 0 = resolved. Falls back to keeping ours if a version can't be parsed, so
# it can never block a merge.
set -uo pipefail

ours="${1:?ours path}"
theirs="${2:?theirs path}"

extract() { grep -oE '[0-9]+\.[0-9]+\.[0-9]+' "$1" 2>/dev/null | head -1; }

vo="$(extract "$ours")"
vt="$(extract "$theirs")"

# If theirs has a strictly higher version, take theirs wholesale; otherwise keep
# ours. (sort -V gives the max as the last line.)
if [ -n "$vo" ] && [ -n "$vt" ] && [ "$vo" != "$vt" ]; then
  higher="$(printf '%s\n%s\n' "$vo" "$vt" | sort -V | tail -1)"
  if [ "$higher" = "$vt" ]; then
    cp -f -- "$theirs" "$ours"
  fi
fi

exit 0
