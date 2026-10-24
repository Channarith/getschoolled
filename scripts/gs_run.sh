#!/usr/bin/env bash
# gs_run.sh - run one long job with hard resource limits and guaranteed cleanup.
#
#   scripts/gs_run.sh [options] -- command [args...]
#
# Every training, translation, transcription or TTS job on the Spark, iBuyPower and Mac
# should start this way. It
#   - refuses to start when free memory is below the machine's reserve (exit 75),
#   - runs the job under systemd-run --user --scope with MemoryMax, MemoryHigh, CPUQuota,
#     IOWeight and TasksMax (Linux), or in its own process group with nice (macOS / no systemd),
#   - takes ~/.gs-gpu.lock when --gpu is set, so only one GPU job runs per machine,
#   - kills the WHOLE job (every child) on exit, Ctrl-C, SIGTERM or timeout: no orphans, no zombies,
#   - writes a job record to ~/.gs-jobs/<id>.json for fleet_status.sh and fleet_reap.sh.
#
# Options
#   --name NAME            label for the job record (default: command name)
#   --gpu                  take the GPU lock first (waits; see --gpu-lock-timeout)
#   --gpu-lock-timeout S   seconds to wait for the GPU lock (default 3600; 0 = fail at once)
#   --min-free-gb G        refuse to start below G GB available (default: the machine reserve)
#   --mem-max GB           override MemoryMax (default: total RAM minus the reserve)
#   --cpus N               override CPU cores the job may use (default: cores minus the reserve)
#   --timeout SEC          kill the job after SEC seconds (exit 124)
#   --nice N               niceness (default from budgets.conf)
#   --machine KEY          budgets.conf section (default: matched by hostname, else "default")
#   --no-systemd           force the process-group fallback on Linux
#   --dry-run              print the resolved plan and exit; nothing is started or locked
# Environment (tests and overrides): GS_BUDGETS_FILE GS_JOBS_DIR GS_GPU_LOCK GS_MACHINE
# Exit codes: the job's own; 124 timeout; 75 not enough free memory or GPU lock busy; 64 bad usage.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUDGETS_FILE="${GS_BUDGETS_FILE:-$ROOT/scripts/fleet/budgets.conf}"
JOBS_DIR="${GS_JOBS_DIR:-$HOME/.gs-jobs}"
GPU_LOCK="${GS_GPU_LOCK:-$HOME/.gs-gpu.lock}"
KILL_GRACE=20

name=""; use_gpu=0; lock_timeout=3600; min_free_gb=""; mem_max_gb=""; cpus_override=""
job_timeout=""; nice_n=""; machine="${GS_MACHINE:-}"; no_systemd=0; dry_run=0

usage() { sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --name) name="${2:?--name needs a value}"; shift ;;
    --gpu) use_gpu=1 ;;
    --gpu-lock-timeout) lock_timeout="${2:?}"; shift ;;
    --min-free-gb) min_free_gb="${2:?}"; shift ;;
    --mem-max) mem_max_gb="${2:?}"; shift ;;
    --cpus) cpus_override="${2:?}"; shift ;;
    --timeout) job_timeout="${2:?}"; shift ;;
    --nice) nice_n="${2:?}"; shift ;;
    --machine) machine="${2:?}"; shift ;;
    --no-systemd) no_systemd=1 ;;
    --dry-run) dry_run=1 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    *) echo "gs_run: unknown option $1 (use -- before the command)" >&2; exit 64 ;;
  esac
  shift
done
if [ $# -eq 0 ]; then echo "gs_run: no command given (put it after --)" >&2; exit 64; fi
cmd=("$@")
[ -n "$name" ] || name="$(basename "${cmd[0]}")"

# ---- budgets.conf (INI) ------------------------------------------------------------------
budget_get() {  # section key -> value
  awk -v sec="$1" -v key="$2" '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ {next}
    /^\[/ {cur=$0; gsub(/[\[\]]/,"",cur); next}
    cur==sec {split($0,kv,"="); k=kv[1]; gsub(/[[:space:]]/,"",k); if (k==key) {v=substr($0,index($0,"=")+1); sub(/[[:space:]]*#.*/,"",v); gsub(/^[[:space:]]+|[[:space:]]+$/,"",v); print v; exit}}
  ' "$BUDGETS_FILE" 2>/dev/null
}
detect_machine() {
  local h sec pat
  h="$(hostname -s 2>/dev/null || hostname)"
  for sec in $(awk '/^\[/ {s=$0; gsub(/[\[\]]/,"",s); print s}' "$BUDGETS_FILE" 2>/dev/null); do
    [ "$sec" = "default" ] && continue
    pat="$(budget_get "$sec" match)"
    if [ -n "$pat" ] && printf '%s' "$h" | grep -Eiq -- "$pat"; then echo "$sec"; return; fi
  done
  echo default
}
[ -n "$machine" ] || machine="$(detect_machine)"
bget() { local v; v="$(budget_get "$machine" "$1")"; [ -n "$v" ] || v="$(budget_get default "$1")"; printf '%s' "$v"; }

reserve_mem_gb="$(bget reserve_mem_gb)"; reserve_mem_gb="${reserve_mem_gb:-4}"
reserve_cores="$(bget reserve_cores)"; reserve_cores="${reserve_cores:-1}"
io_weight="$(bget io_weight)"; io_weight="${io_weight:-50}"
tasks_max="$(bget tasks_max)"; tasks_max="${tasks_max:-4096}"
mem_high_pct="$(bget mem_high_pct)"; mem_high_pct="${mem_high_pct:-90}"
[ -n "$nice_n" ] || nice_n="$(bget nice)"; nice_n="${nice_n:-10}"
[ -n "$min_free_gb" ] || min_free_gb="$reserve_mem_gb"

# ---- machine facts -----------------------------------------------------------------------
os="$(uname -s)"
if [ "$os" = "Darwin" ]; then
  cpus="$(sysctl -n hw.ncpu 2>/dev/null || echo 1)"
  total_kb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 ))
  pagesz="$(vm_stat 2>/dev/null | awk '/page size of/ {print $8}')"
  case "$pagesz" in ''|*[!0-9]*) pagesz=4096 ;; esac
  freepages="$(vm_stat 2>/dev/null | awk '/Pages (free|inactive|speculative)/ {gsub(/\./,"",$NF); s+=$NF} END{print s+0}')"
  avail_kb=$(( freepages * pagesz / 1024 ))
else
  cpus="$(nproc 2>/dev/null || echo 1)"
  total_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null)"; total_kb="${total_kb:-0}"
  avail_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null)"; avail_kb="${avail_kb:-0}"
fi

# ---- limits ------------------------------------------------------------------------------
reserve_kb=$(( reserve_mem_gb * 1048576 ))
if [ -n "$mem_max_gb" ]; then mem_max_kb=$(( mem_max_gb * 1048576 )); else mem_max_kb=$(( total_kb - reserve_kb )); fi
[ "$mem_max_kb" -ge 1048576 ] || mem_max_kb=1048576
mem_high_kb=$(( mem_max_kb * mem_high_pct / 100 ))
if [ -n "$cpus_override" ]; then job_cores="$cpus_override"; else job_cores=$(( cpus - reserve_cores )); fi
[ "$job_cores" -ge 1 ] || job_cores=1
cpu_quota=$(( job_cores * 100 ))
min_free_kb=$(( min_free_gb * 1048576 ))

use_systemd=0
if [ "$os" = "Linux" ] && [ "$no_systemd" = 0 ] && command -v systemd-run >/dev/null 2>&1 \
   && systemctl --user show-environment >/dev/null 2>&1; then
  use_systemd=1
fi

id="$(date +%Y%m%d-%H%M%S)-$$"
unit="gs-$id"
mode="process-group"; [ "$use_systemd" = 1 ] && mode="systemd-scope"

json_escape() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n\t' '  '; }

if [ "$dry_run" = 1 ]; then
  echo "gs_run plan (dry run, nothing started)"
  echo "  machine:      $machine ($os, $cpus cores, $((total_kb / 1048576)) GB RAM, $((avail_kb / 1048576)) GB available now)"
  echo "  mode:         $mode"
  echo "  mem_max_gb:   $((mem_max_kb / 1048576))   mem_high_gb: $((mem_high_kb / 1048576))   (reserve ${reserve_mem_gb} GB stays free)"
  echo "  cpu_quota:    ${cpu_quota}%  ($job_cores of $cpus cores; reserve $reserve_cores)"
  echo "  nice:         $nice_n   io_weight: $io_weight   tasks_max: $tasks_max"
  echo "  gpu_lock:     $([ "$use_gpu" = 1 ] && echo "yes ($GPU_LOCK, wait ${lock_timeout}s)" || echo no)"
  echo "  timeout:      ${job_timeout:-none}"
  echo "  min_free_gb:  $min_free_gb  -> $([ "$avail_kb" -ge "$min_free_kb" ] && echo "would start" || echo "would REFUSE (exit 75)")"
  echo "  job_record:   $JOBS_DIR/$id.json"
  echo "  command:      ${cmd[*]}"
  exit 0
fi

if [ "$avail_kb" -lt "$min_free_kb" ]; then
  echo "gs_run: only $((avail_kb / 1048576)) GB memory available, need at least $min_free_gb GB free. Not starting '$name'." >&2
  echo "gs_run: see scripts/fleet_status.sh and scripts/fleet_reap.sh for what is using it." >&2
  exit 75
fi

mkdir -p "$JOBS_DIR"
record="$JOBS_DIR/$id.json"
started_epoch="$(date +%s)"
state="running"; exit_code=""; ended_epoch=""; child_pid=""; timed_out=0

write_record() {
  local tmp="$record.tmp.$$"
  {
    printf '{"id": "%s", "name": "%s", "state": "%s", "pid": %s, "child_pid": %s, "unit": "%s", ' \
      "$id" "$(json_escape "$name")" "$state" "$$" "${child_pid:-null}" "$([ "$use_systemd" = 1 ] && echo "$unit.scope")"
    printf '"machine": "%s", "mode": "%s", "gpu": %s, ' "$machine" "$mode" "$([ "$use_gpu" = 1 ] && echo true || echo false)"
    printf '"limits": {"mem_max_gb": %s, "mem_high_gb": %s, "cpu_quota_pct": %s, "nice": %s, "io_weight": %s, "tasks_max": %s}, ' \
      "$((mem_max_kb / 1048576))" "$((mem_high_kb / 1048576))" "$cpu_quota" "$nice_n" "$io_weight" "$tasks_max"
    printf '"started": %s, "ended": %s, "exit_code": %s, "cmd": "%s"}\n' \
      "$started_epoch" "${ended_epoch:-null}" "${exit_code:-null}" "$(json_escape "${cmd[*]}")"
  } > "$tmp" && mv "$tmp" "$record"
}

# ---- GPU lock ----------------------------------------------------------------------------
lock_held=0
lock_dir="$GPU_LOCK.dir"
acquire_gpu_lock() {
  mkdir -p "$(dirname "$GPU_LOCK")"
  if command -v flock >/dev/null 2>&1; then
    exec 9>>"$GPU_LOCK"
    if [ "$lock_timeout" -le 0 ]; then flock -n 9 || return 1; else flock -w "$lock_timeout" 9 || return 1; fi
  else
    local waited=0
    while ! mkdir "$lock_dir" 2>/dev/null; do
      local holder; holder="$(cat "$lock_dir/pid" 2>/dev/null)"
      if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then rm -rf "$lock_dir"; continue; fi
      [ "$waited" -ge "$lock_timeout" ] && return 1
      sleep 2; waited=$((waited + 2))
    done
    echo "$$" > "$lock_dir/pid"
  fi
  lock_held=1
  printf '%s %s %s %s\n' "$$" "$id" "$name" "$started_epoch" > "$GPU_LOCK.owner"
  return 0
}
release_gpu_lock() {
  [ "$lock_held" = 1 ] || return 0
  rm -f "$GPU_LOCK.owner"
  if command -v flock >/dev/null 2>&1; then exec 9>&-; else rm -rf "$lock_dir"; fi
  lock_held=0
}

# ---- cleanup: the whole job dies with this script ----------------------------------------
cleaned=0
kill_job() {
  if [ "$use_systemd" = 1 ]; then
    systemctl --user stop "$unit.scope" >/dev/null 2>&1
    systemctl --user kill --signal=SIGKILL "$unit.scope" >/dev/null 2>&1
  elif [ -n "$child_pid" ]; then
    kill -TERM -- "-$child_pid" 2>/dev/null
    local i=0
    while kill -0 -- "-$child_pid" 2>/dev/null && [ "$i" -lt "$KILL_GRACE" ]; do sleep 1; i=$((i + 1)); done
    kill -KILL -- "-$child_pid" 2>/dev/null
  fi
}
cleanup() {
  [ "$cleaned" = 1 ] && return
  cleaned=1
  [ -n "${watchdog_pid:-}" ] && kill "$watchdog_pid" 2>/dev/null
  kill_job
  ended_epoch="$(date +%s)"
  if [ "$timed_out" = 1 ]; then state="timeout"
  elif [ "$state" = "killed" ]; then :
  elif [ "${exit_code:-1}" = 0 ]; then state="finished"
  else state="failed"; fi
  write_record
  release_gpu_lock
}
on_signal() { exit_code="${1:-143}"; state="killed"; cleanup; exit "$exit_code"; }
trap cleanup EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM HUP

if [ "$use_gpu" = 1 ]; then
  if ! acquire_gpu_lock; then
    echo "gs_run: GPU lock $GPU_LOCK is busy (owner: $(cat "$GPU_LOCK.owner" 2>/dev/null || echo unknown)). Not starting '$name'." >&2
    exit_code=75; state="failed"; cleaned=0
    exit 75
  fi
  # training/spark_nightly.sh takes the same lock itself unless this is set; without it the job would
  # wait forever on the lock this wrapper already holds.
  export GS_GPU_LOCK_HELD=1
fi

write_record
echo "gs_run: started '$name' as $id ($mode, mem<=$((mem_max_kb / 1048576))G, cpu<=${cpu_quota}%, nice $nice_n)" >&2

# ---- run ---------------------------------------------------------------------------------
if [ "$use_systemd" = 1 ]; then
  systemd-run --user --scope --quiet --collect --unit="$unit" \
    -p "MemoryMax=${mem_max_kb}K" -p "MemoryHigh=${mem_high_kb}K" -p "CPUQuota=${cpu_quota}%" \
    -p "IOWeight=$io_weight" -p "TasksMax=$tasks_max" \
    -- nice -n "$nice_n" "${cmd[@]}" 9>&- &
  child_pid=$!
else
  set -m
  run=("${cmd[@]}")
  [ "$os" = "Darwin" ] && command -v caffeinate >/dev/null 2>&1 && run=(caffeinate -i "${run[@]}")
  nice -n "$nice_n" "${run[@]}" 9>&- &
  child_pid=$!
  set +m
fi
if [ -n "$job_timeout" ]; then
  # Short sleeps, so cleanup never leaves a long sleep behind. Marks the timeout in a file
  # (a subshell cannot set our variables), then kills the whole job.
  (
    i=0
    while [ "$i" -lt "$job_timeout" ]; do
      sleep 1; i=$((i + 1))
      kill -0 "$child_pid" 2>/dev/null || exit 0
    done
    : > "$record.timeout"
    kill_job
  ) 9>&- &
  watchdog_pid=$!
fi
write_record

wait "$child_pid"
exit_code=$?
if [ -f "$record.timeout" ]; then timed_out=1; exit_code=124; rm -f "$record.timeout"; fi
cleanup
exit "$exit_code"
