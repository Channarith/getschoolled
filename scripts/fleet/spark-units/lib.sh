#!/usr/bin/env bash
# Shared helpers for the Spark's long-running service scripts (sourced, never executed).
#
# What they guarantee:
#   - a child job runs in its own process group (set -m), and a SIGTERM/SIGINT to the loop terminates that whole group,
#     waits a grace period, then SIGKILLs it: no orphans, no zombies, no restart storms;
#   - sleeps are interruptible, so "systemctl stop" is never held up by a 3600 s sleep;
#   - the loop exits cleanly (status 0) after a stop request.
# Test hook: AOEP_FOREVER_ONCE=1 makes a loop stop after one iteration.

SU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SU_ROOT="$(cd "${SU_DIR}/../../.." && pwd)"
SU_STOP=0
SU_CHILD=""
SU_GRACE="${AOEP_STOP_GRACE_S:-20}"

set -m 2>/dev/null || true

su_log() { printf '=== %s %s ===\n' "$*" "$(date -Is)"; }

su_free_mb() { awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null; }

# Interruptible sleep: `sleep N & wait $!` returns as soon as a trapped signal arrives.
su_sleep() {
  sleep "${1:-1}" &
  local sp=$!
  wait "$sp" 2>/dev/null
  kill "$sp" 2>/dev/null || true
}

# Called by the TERM/INT trap: ask the child's process group to stop, escalate after the grace period.
su_on_term() {
  SU_STOP=1
  if [ -n "${SU_CHILD}" ] && kill -0 "${SU_CHILD}" 2>/dev/null; then
    su_log "stop requested: terminating process group ${SU_CHILD}"
    kill -TERM -- "-${SU_CHILD}" 2>/dev/null || kill -TERM "${SU_CHILD}" 2>/dev/null || true
    local i=0
    while kill -0 "${SU_CHILD}" 2>/dev/null && [ "$i" -lt "${SU_GRACE}" ]; do
      sleep 1
      i=$((i + 1))
    done
    if kill -0 "${SU_CHILD}" 2>/dev/null; then
      su_log "child ignored SIGTERM for ${SU_GRACE}s: SIGKILL"
      kill -KILL -- "-${SU_CHILD}" 2>/dev/null || kill -KILL "${SU_CHILD}" 2>/dev/null || true
    fi
  fi
}

trap su_on_term TERM INT

# Run a command as a child in its own process group and wait for it. Returns its exit status
# (143 when we stopped it because the loop was told to stop).
su_run_child() {
  "$@" &
  SU_CHILD=$!
  wait "${SU_CHILD}"
  local rc=$?
  # `wait` returns early (>128) when our trap fired; let the trap finish stopping the child, then collect it.
  if [ "${SU_STOP}" = 1 ]; then
    wait "${SU_CHILD}" 2>/dev/null
    rc=143
  fi
  SU_CHILD=""
  return "${rc}"
}

# Wait (up to 10 minutes, as before) until MemAvailable >= need_mb. Stops waiting on a stop request.
su_wait_memory() {
  local need_mb="$1" label="${2:-job}" free_mb i
  for i in $(seq 1 30); do
    [ "${SU_STOP}" = 1 ] && return 0
    free_mb="$(su_free_mb)"
    if [ -z "${free_mb}" ] || [ "${free_mb}" -ge "${need_mb}" ]; then
      su_log "${label} memory ok free_mb=${free_mb}"
      return 0
    fi
    su_log "${label} waiting free_mb=${free_mb} need_mb=${need_mb}"
    su_sleep 20
  done
}

su_once_done() { [ "${AOEP_FOREVER_ONCE:-0}" = 1 ]; }
