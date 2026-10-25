#!/usr/bin/env bash
# Read-only: how many audio courses are "Ready" per language on the live site (GET /audio/search; no login, nothing is changed).
#   scripts/check_translations_live.sh [BASE_URL]        (default https://salareen.com)
set -uo pipefail
BASE="${1:-${SALAREEN_URL:-https://salareen.com}}"
LANGS="${CHECK_LANGS:-km yue es zh fr it th vi hi ja ko pt de ru ar id tr pl nl uk he bn fa ur el cs sw tl}"
code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$BASE/audio/search?language=es&limit=1")
case "$code" in
  200) ;;
  404) echo "GET /audio/search answers 404: the curriculum service with the search endpoint (v0.97.81+) is not deployed yet." ; exit 2 ;;
  *) echo "GET /audio/search answered HTTP $code" ; exit 2 ;;
esac
printf "%-6s %7s %7s\n" lang ready total
for l in $LANGS; do
  curl -s -m 25 "$BASE/audio/search?language=$l&include_english=true&limit=1" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print('%-6s %7s %7s' % ('$l','?','?')); raise SystemExit
print('%-6s %7s %7s' % (d.get('language','$l'), d.get('ready_in_language','?'), d.get('total','?')))"
done
