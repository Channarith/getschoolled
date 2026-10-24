#!/usr/bin/env bash
# Wake the llama-server and make sure its model is loaded BEFORE the bake-off starts.
#
# Why: the server runs with --sleep-idle-seconds 600, so it unloads its ~20 GB model after 10 idle minutes and
# reloads it ("fitting params to device memory ...") on the next request. The bake-off client used to be that
# request, so its first replies stalled for minutes and the balance monitor judged it "crawling". One tiny request
# here pays the reload once, up front, outside any timing window.
#
# It never changes the server's own flags (see README.txt for how to inspect or change --sleep-idle-seconds).
# Best effort by default: exits 0 even when the server is absent or slow, so a missing server never blocks a
# training cycle. --strict makes failure exit 1.
#
# Usage: llama-warm.sh [--url http://127.0.0.1:8342] [--model ALIAS] [--timeout SECONDS] [--strict]
#   defaults: --url $BALANCE_LLAMA_URL or http://127.0.0.1:8342, --model $SERVE_MODEL or qwen3.6-35b-a3b, --timeout 900
set -u
URL="${BALANCE_LLAMA_URL:-http://127.0.0.1:8342}"
MODEL="${SERVE_MODEL:-qwen3.6-35b-a3b}"
TIMEOUT=900
STRICT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --url) URL="${2:?}"; shift ;;
    --model) MODEL="${2:?}"; shift ;;
    --timeout) TIMEOUT="${2:?}"; shift ;;
    --strict) STRICT=1 ;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "llama-warm: unknown option $1" >&2; exit 64 ;;
  esac
  shift
done
URL="${URL%/}"; URL="${URL%/v1}"

say() { printf '[llama-warm] %s\n' "$*"; }
fail() { say "$*"; [ "${STRICT}" = 1 ] && exit 1; exit 0; }

code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "${URL}/health" 2>/dev/null || true)"
case "${code}" in
  200|503) ;;                                  # up (ready, or loading)
  *) fail "no llama-server answering at ${URL} (health=${code:-none}); nothing to warm" ;;
esac

sleeping="$(curl -s -m 5 "${URL}/props" 2>/dev/null | grep -o '"is_sleeping"[[:space:]]*:[[:space:]]*true' || true)"
[ -n "${sleeping}" ] && say "server is sleeping: waking it (reload can take minutes)" || say "server awake (health=${code}); sending a 1-token request to make sure the model is resident"

start="$(date +%s)"
body="$(printf '{"model":"%s","messages":[{"role":"user","content":"Reply with OK."}],"max_tokens":1,"temperature":0}' "${MODEL}")"
rcode="$(curl -s -o /dev/null -m "${TIMEOUT}" -w '%{http_code}' -H 'Content-Type: application/json' -d "${body}" "${URL}/v1/chat/completions" 2>/dev/null || true)"
elapsed=$(( $(date +%s) - start ))
if [ "${rcode}" != "200" ]; then
  fail "warm-up request failed (http=${rcode:-none}) after ${elapsed}s"
fi
still="$(curl -s -m 5 "${URL}/props" 2>/dev/null | grep -o '"is_sleeping"[[:space:]]*:[[:space:]]*true' || true)"
[ -n "${still}" ] && fail "server went back to sleep right after warm-up (${elapsed}s)"
say "warm: model answered in ${elapsed}s"
exit 0
