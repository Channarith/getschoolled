#!/usr/bin/env bash
# Resource limits for long training stages. Source this file; it defines gs_stage.
#
#   . training/lib_limits.sh
#   gs_stage "train" 240 python3 training/run_finetune.py ...
#
# Budget (so a job can never starve the machine):
#   spark      keep >= 16 GB RAM and 2 cores free; abort a stage if free RAM drops under 6 GB
#   ibuypower  keep >=  6 GB RAM and 2 cores free; abort under 3 GB
# Profile comes from GS_PROFILE, else the hostname (Spark / Kal-el), else the RAM size.
# Every number can be overridden: GS_RESERVE_GB, GS_RESERVE_CORES, GS_ABORT_FREE_GB.
#
# How a stage is limited, best first:
#   1. scripts/gs_run.sh (the fleet runner) when present: it gets --name, --timeout, --mem-max and
#      --cpus and writes the job record fleet_status.sh reads. It is NOT given --gpu here, because
#      spark_nightly.sh already holds ~/.gs-gpu.lock (taking it twice would deadlock).
#   2. systemd-run --user --scope with MemoryMax / MemorySwapMax=0 / CPUQuota (hard cgroup limits).
#   3. a plain process group with timeout. The free-RAM watchdog below runs in every mode.
# No orphans: each stage is its own process group, killed on timeout, Ctrl-C, SIGTERM or abort;
# the watchdog is reaped; children are waited for so no zombie is left behind.
#
# Exit codes from gs_stage: the command's own, 124 timeout, 75 aborted to protect the host.
# Tests shrink time: GS_TIMEOUT_SCALE=1 (seconds per "minute"), GS_KILL_AFTER=2, GS_MEM_CHECK_EVERY=1,
# GS_FAKE_AVAIL_GB=<n> / GS_FAKE_TOTAL_GB=<n> to simulate memory sizes.

GS_ROOT="${GS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
GS_CHILD=""
GS_WATCH=""
GS_INIT_DONE=""
GS_ABORT_FLAG=""

gs_total_gb() { if [ -n "${GS_FAKE_TOTAL_GB:-}" ]; then echo "$GS_FAKE_TOTAL_GB"; return; fi; awk '/^MemTotal:/{printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null; }
gs_avail_gb() { if [ -n "${GS_FAKE_AVAIL_GB:-}" ]; then echo "$GS_FAKE_AVAIL_GB"; return; fi; awk '/^MemAvailable:/{printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null; }
gs_cores() { nproc 2>/dev/null || echo 1; }

gs_init() {
  [ -n "$GS_INIT_DONE" ] && return 0
  local host total
  host="$(hostname 2>/dev/null | tr 'A-Z' 'a-z')"
  total="$(gs_total_gb)"
  if [ -z "${GS_PROFILE:-}" ]; then
    case "$host" in
      *spark*) GS_PROFILE=spark ;;
      *kal-el*|*kalel*|*ibuypower*) GS_PROFILE=ibuypower ;;
      *) if [ "${total:-0}" -ge 100 ]; then GS_PROFILE=spark; elif [ "${total:-0}" -ge 16 ]; then GS_PROFILE=ibuypower; else GS_PROFILE=generic; fi ;;
    esac
  fi
  case "$GS_PROFILE" in
    spark)     : "${GS_RESERVE_GB:=16}"; : "${GS_RESERVE_CORES:=2}"; : "${GS_ABORT_FREE_GB:=6}" ;;
    ibuypower) : "${GS_RESERVE_GB:=6}";  : "${GS_RESERVE_CORES:=2}"; : "${GS_ABORT_FREE_GB:=3}" ;;
    *)         : "${GS_RESERVE_GB:=4}";  : "${GS_RESERVE_CORES:=1}"; : "${GS_ABORT_FREE_GB:=2}" ;;
  esac
  local cores
  cores="$(gs_cores)"
  # Unknown total RAM (not Linux): no ceiling, rather than a negative one.
  if [ -n "$total" ] && [ "$total" -gt "$GS_RESERVE_GB" ]; then GS_MEM_MAX_GB="$(( total - GS_RESERVE_GB ))"; else GS_MEM_MAX_GB=""; fi
  GS_CPU_QUOTA="$(( (cores - GS_RESERVE_CORES) * 100 ))"
  [ "$GS_CPU_QUOTA" -lt 100 ] && GS_CPU_QUOTA=100
  GS_RUN="${GS_RUN:-$GS_ROOT/scripts/gs_run.sh}"
  GS_INIT_DONE=1
}

# Refuse to start when free RAM is already under reserve + what the stage needs.
gs_preflight() {
  gs_init
  local need="${1:-0}" avail
  avail="$(gs_avail_gb)"
  [ -z "$avail" ] && return 0   # not Linux: nothing to measure
  if [ "$avail" -lt "$(( GS_RESERVE_GB + need ))" ]; then
    echo "REFUSING TO START: ${avail} GB RAM free, need ${need} GB plus ${GS_RESERVE_GB} GB kept free for the host (profile=$GS_PROFILE)." >&2
    echo "Free memory first (see docs/training-spark-runbook.txt, step 2), then rerun." >&2
    return 75
  fi
}

gs_kill_group() {
  # $1 = signal. Kill the stage's whole process group, not just its leader.
  [ -n "$GS_CHILD" ] && kill "-$1" -- "-$GS_CHILD" 2>/dev/null
  return 0
}

gs_cleanup() {
  if [ -n "$GS_WATCH" ]; then kill "$GS_WATCH" 2>/dev/null; wait "$GS_WATCH" 2>/dev/null; GS_WATCH=""; fi
  if [ -n "$GS_CHILD" ] && kill -0 "$GS_CHILD" 2>/dev/null; then
    gs_kill_group TERM
    sleep 3
    kill -0 "$GS_CHILD" 2>/dev/null && gs_kill_group KILL
    wait "$GS_CHILD" 2>/dev/null
  fi
  GS_CHILD=""
}

gs_have_scope() {
  command -v systemd-run >/dev/null 2>&1 || return 1
  systemd-run --user --scope --quiet --collect -p MemoryMax=1G true >/dev/null 2>&1
}

gs_run_supported() {
  [ -x "$GS_RUN" ] && "$GS_RUN" --help 2>&1 | grep -q -- "--timeout"
}

# gs_stage NAME TIMEOUT_MINUTES command [args...]
gs_stage() {
  gs_init
  local name="$1" tmin="$2"
  shift 2
  local tdir
  tdir="$(mktemp -d "${TMPDIR:-/tmp}/gs-stage.XXXXXX")"
  GS_ABORT_FLAG="$tdir/abort"
  local tflag="$tdir/timeout"
  local limit_s="$(( tmin * ${GS_TIMEOUT_SCALE:-60} ))"
  local mode="process-group"
  local -a runner=()
  if gs_run_supported; then
    mode="gs_run.sh"
  elif gs_have_scope; then
    mode="systemd-scope"
    runner=(systemd-run --user --scope --quiet --collect -p MemorySwapMax=0 -p "CPUQuota=${GS_CPU_QUOTA}%")
    [ -n "$GS_MEM_MAX_GB" ] && runner+=(-p "MemoryMax=${GS_MEM_MAX_GB}G")
  fi
  echo "[$name] limits: RAM<=${GS_MEM_MAX_GB:-unlimited}G cpu<=${GS_CPU_QUOTA}% timeout=${tmin}m abort-if-free<${GS_ABORT_FREE_GB}G mode=$mode profile=$GS_PROFILE"

  trap 'gs_cleanup; rm -rf "$tdir"; exit 143' INT TERM
  trap 'gs_cleanup' EXIT
  set -m
  if [ "$mode" = "gs_run.sh" ]; then
    "$GS_RUN" --name "$name" --timeout "$limit_s" ${GS_MEM_MAX_GB:+--mem-max "$GS_MEM_MAX_GB"} \
      --cpus "$(( GS_CPU_QUOTA / 100 ))" -- "$@" &
  else
    ${runner[@]+"${runner[@]}"} "$@" &
  fi
  GS_CHILD=$!
  set +m

  # Supervisor: enforces the timeout and the free-RAM floor, then stays out of the way.
  local aflag="$GS_ABORT_FLAG" floor="$GS_ABORT_FREE_GB" child="$GS_CHILD"
  local kill_after="${GS_KILL_AFTER:-60}" every="${GS_MEM_CHECK_EVERY:-10}"
  # gs_run enforces the same timeout itself; ours is a backstop that fires only if gs_run does not.
  [ "$mode" = "gs_run.sh" ] && limit_s="$(( limit_s + 30 ))"
  (
    start="$(date +%s)"
    i=0
    while kill -0 "$child" 2>/dev/null; do
      sleep 1
      i=$(( i + 1 ))
      if [ "$(( $(date +%s) - start ))" -ge "$limit_s" ]; then
        echo "[$name] TIMEOUT after ${tmin}m; stopping the stage." >&2
        : > "$tflag"
        kill -TERM -- "-$child" 2>/dev/null
        sleep "$kill_after"
        kill -KILL -- "-$child" 2>/dev/null
        exit 0
      fi
      if [ "$(( i % every ))" -eq 0 ]; then
        free="$(gs_avail_gb)"
        if [ -n "$free" ] && [ "$free" -lt "$floor" ]; then
          echo "[$name] ABORT: only ${free} GB RAM free (floor ${floor} GB); stopping the stage to protect the host." >&2
          : > "$aflag"
          kill -TERM -- "-$child" 2>/dev/null
          sleep "$kill_after"
          kill -KILL -- "-$child" 2>/dev/null
          exit 0
        fi
      fi
    done
  ) &
  GS_WATCH=$!

  local rc=0
  wait "$GS_CHILD" || rc=$?
  kill "$GS_WATCH" 2>/dev/null
  wait "$GS_WATCH" 2>/dev/null
  GS_WATCH=""
  GS_CHILD=""
  local result="$rc"
  if [ -e "$aflag" ]; then
    echo "[$name] aborted to protect the host (exit 75)" >&2
    result=75
  elif [ -e "$tflag" ]; then
    echo "[$name] hit its ${tmin} minute timeout (exit 124)" >&2
    result=124
  fi
  rm -rf "$tdir"
  trap - INT TERM EXIT
  return "$result"
}
