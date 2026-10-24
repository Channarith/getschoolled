#!/usr/bin/env bash
# Four lines on what decides whether a demo job can start on THIS machine (run on the Spark; fleet_status.sh pipes it
# over ssh). Read-only.
#
#   GPU lock : who holds ~/.gs-gpu.lock, for how long, at what priority (or free)
#   Memory   : MemAvailable against the 16 GB gs_run.sh gate (OK / BLOCKED)
#   Labs     : enrollment page :8780 and listening lab :8790 listening or DOWN
#   Queue    : gs_run.sh jobs waiting for the GPU lock (names, oldest wait)
#
# Environment: GS_GPU_LOCK (default ~/.gs-gpu.lock)  GS_GATE_GB (default 16)  GS_ENROLL_PORT  GS_LAB_PORT
# (tests: GS_GATE_FAKE_AVAIL_GB)
set -u
LOCK="${GS_GPU_LOCK:-$HOME/.gs-gpu.lock}"
GATE_GB="${GS_GATE_GB:-16}"
ENROLL_PORT="${GS_ENROLL_PORT:-8780}"
LAB_PORT="${GS_LAB_PORT:-8790}"

human() {  # seconds -> 2h05m / 7m / 40s
  local s="${1:-0}"
  if [ "$s" -ge 3600 ]; then printf '%dh%02dm' $((s / 3600)) $((s % 3600 / 60)); elif [ "$s" -ge 60 ]; then printf '%dm' $((s / 60)); else printf '%ds' "$s"; fi
}
age_of() { ps -o etimes= -p "$1" 2>/dev/null | tr -d ' '; }

holder_pid=""
holder_line=""
if [ -r "$LOCK.owner" ] && read -r opid _oid oname _ostart oprio < "$LOCK.owner" && [ -n "${opid:-}" ] && kill -0 "$opid" 2>/dev/null; then
  holder_pid="$opid"
  holder_line="held by '${oname}' (pid ${opid}, ${oprio:-interactive}, running $(human "$(age_of "$opid")"))"
elif command -v pgrep >/dev/null 2>&1; then
  fl="$(pgrep -f "flock .*gs-gpu.lock" 2>/dev/null | head -n 1)"
  if [ -n "$fl" ]; then
    holder_pid="$fl"
    holder_line="held by an unregistered flock (pid ${fl}, running $(human "$(age_of "$fl")")): $(ps -o args= -p "$fl" 2>/dev/null | cut -c1-90)"
  fi
fi
echo "GPU lock : ${holder_line:-free}"

avail_gb="${GS_GATE_FAKE_AVAIL_GB:-}"
if [ -z "$avail_gb" ] && [ -r /proc/meminfo ]; then avail_gb="$(awk '/^MemAvailable:/ {printf "%d", $2/1048576}' /proc/meminfo)"; fi
if [ -n "$avail_gb" ]; then
  if [ "$avail_gb" -ge "$GATE_GB" ]; then verdict=OK; else verdict="BLOCKED: gs_run.sh will refuse to start a job"; fi
  echo "Memory   : ${avail_gb} GB available, gate ${GATE_GB} GB: ${verdict}"
else
  echo "Memory   : unknown (no /proc/meminfo)"
fi

listening() {  # port -> yes/no
  if command -v ss >/dev/null 2>&1; then ss -ltn 2>/dev/null | awk -v p=":$1" '$4 ~ p"$" {f=1} END {exit !f}'
  else (exec 3<>"/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1; fi
}
l1="DOWN"; l2="DOWN"
listening "$ENROLL_PORT" && l1="listening"
listening "$LAB_PORT" && l2="listening"
echo "Labs     : enrollment :${ENROLL_PORT} ${l1}, listening lab :${LAB_PORT} ${l2}"

waiters=""; n=0; oldest=0
if command -v pgrep >/dev/null 2>&1; then
  for pid in $(pgrep -f "gs_run.sh .*--gpu" 2>/dev/null); do
    [ "$pid" = "$holder_pid" ] && continue
    [ "$pid" = "$$" ] && continue
    args="$(ps -o args= -p "$pid" 2>/dev/null)"
    # a real gs_run.sh process, not a shell whose command line merely mentions it, and not a subshell of a running job
    printf '%s' "$args" | grep -Eq '^(/[^ ]*/)?bash [^ ]*gs_run\.sh ' || continue
    ppid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
    ps -o args= -p "${ppid:-0}" 2>/dev/null | grep -Eq '^(/[^ ]*/)?bash [^ ]*gs_run\.sh ' && continue
    nm="$(printf '%s' "$args" | sed -n 's/.*--name \([^ ]*\).*/\1/p')"
    a="$(age_of "$pid")"; a="${a:-0}"
    n=$((n + 1)); [ "$a" -gt "$oldest" ] && oldest="$a"
    waiters="${waiters}${waiters:+, }${nm:-?}"
  done
fi
if [ "$n" = 0 ]; then echo "Queue    : nothing waiting"; else echo "Queue    : ${n} waiting (${waiters}); oldest $(human "$oldest")"; fi
