#!/usr/bin/env bash
# fleet_reap.sh - find and (only with --yes) clean up dead weight on THIS machine.
#
#   scripts/fleet_reap.sh                    dry run: list what it would do, change nothing
#   scripts/fleet_reap.sh --yes              act on gs_run jobs, dead job records and a stale GPU lock note
#   scripts/fleet_reap.sh --zombie-parents --yes   also send TERM to the parents of zombies
#   scripts/fleet_reap.sh --pid 1234 --yes   stop one specific process you name (TERM, then KILL after 10 s)
#   scripts/fleet_reap.sh --include-idle     also treat gs_run jobs with no CPU progress as stoppable
#   scripts/fleet_reap.sh --scope records,jobs,zombies,lock,pids   limit what is examined
#
# It only touches: (1) jobs started through scripts/gs_run.sh (recorded in ~/.gs-jobs),
# (2) records of jobs whose process is gone, (3) a stale ~/.gs-gpu.lock.owner file,
# (4) parents of zombies, and only with --zombie-parents, (5) PIDs you pass with --pid.
# Anything else is never stopped. Run it on the machine itself, e.g.
#   ssh -t spark 'cd ~/code/getschoolled && scripts/fleet_reap.sh'
set -uo pipefail

JOBS_DIR="${GS_JOBS_DIR:-$HOME/.gs-jobs}"
GPU_LOCK="${GS_GPU_LOCK:-$HOME/.gs-gpu.lock}"
RUNAWAY_CPU=300
RUNAWAY_SECONDS=1800
IDLE_SAMPLE=10
yes=0; zombie_parents=0; include_idle=0; scope="records,jobs,zombies,lock,pids"
pids=()

while [ $# -gt 0 ]; do
  case "$1" in
    --yes) yes=1 ;;
    --zombie-parents) zombie_parents=1 ;;
    --include-idle) include_idle=1 ;;
    --pid) pids+=("${2:?--pid needs a number}"); shift ;;
    --scope) scope="${2:?}"; shift ;;
    --runaway-cpu) RUNAWAY_CPU="${2:?}"; shift ;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "fleet_reap: unknown option $1" >&2; exit 64 ;;
  esac
  shift
done

in_scope() { case ",$scope," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
say() { printf '%s\n' "$*"; }
if [ "$yes" = 1 ]; then say "fleet_reap: ACTING (--yes) on $(hostname -s)"; else say "fleet_reap: dry run on $(hostname -s) (nothing is stopped; add --yes to act)"; fi

etime_s() {  # [[dd-]hh:]mm:ss -> seconds
  awk -v t="$1" 'BEGIN {d=0; if (index(t,"-")) {split(t,a,"-"); d=a[1]; t=a[2]} n=split(t,p,":"); s=0; for(i=1;i<=n;i++) s=s*60+p[i]; print d*86400+s}'
}
cpu_s() {  # cputime [[dd-]hh:]mm:ss[.cc] -> whole seconds
  awk -v t="$1" 'BEGIN {d=0; if (index(t,"-")) {split(t,a,"-"); d=a[1]; t=a[2]} n=split(t,p,":"); s=0; for(i=1;i<=n;i++) s=s*60+p[i]; printf "%d", d*86400+s}'
}
alive() { kill -0 "$1" 2>/dev/null; }
stat_of() { ps -o stat= -p "$1" 2>/dev/null | tr -d ' '; }
args_of() { ps -o args= -p "$1" 2>/dev/null | cut -c1-110; }

stop_pid() {  # pid why  (TERM, wait 10 s, KILL)
  local pid="$1" why="$2"
  if [ "$yes" != 1 ]; then say "  would stop pid $pid ($why): $(args_of "$pid")"; return; fi
  say "  stopping pid $pid ($why): $(args_of "$pid")"
  kill -TERM "$pid" 2>/dev/null
  local i=0
  while alive "$pid" && [ "$(stat_of "$pid")" != "Z" ] && [ "$i" -lt 10 ]; do sleep 1; i=$((i + 1)); done
  if alive "$pid" && [ "$(stat_of "$pid")" != "Z" ]; then kill -KILL "$pid" 2>/dev/null; fi
}
protected_parent() {  # pid -> 0 if it must never be signalled
  local pid="$1" a
  [ "$pid" = 1 ] && return 0
  [ "$pid" = "$$" ] && return 0
  a="$(args_of "$pid")"
  case "$a" in
    *sshd*|*systemd*|*launchd*|*login*|*-bash|*-zsh|*/bash|*/zsh|bash|zsh|fish|*tmux*|*screen*|*Terminal*|*iTerm*) return 0 ;;
  esac
  return 1
}

mark_record() {  # file newstate
  local f="$1" st="$2" now tmp
  now="$(date +%s)"
  tmp="$f.tmp.$$"
  sed -e "s/\"state\": \"running\"/\"state\": \"$st\"/" -e "s/\"ended\": null/\"ended\": $now/" "$f" > "$tmp" && mv "$tmp" "$f"
}

if in_scope records || in_scope jobs; then
  say "gs_run jobs ($JOBS_DIR):"
  found=0
  for f in "$JOBS_DIR"/*.json; do
    [ -f "$f" ] || continue
    grep -q '"state": "running"' "$f" || continue
    found=1
    id="$(sed -n 's/.*"id": "\([^"]*\)".*/\1/p' "$f" | head -1)"
    jname="$(sed -n 's/.*"name": "\([^"]*\)".*/\1/p' "$f" | head -1)"
    wpid="$(sed -n 's/.*"pid": \([0-9][0-9]*\).*/\1/p' "$f" | head -1)"
    cpid="$(sed -n 's/.*"child_pid": \([0-9][0-9]*\).*/\1/p' "$f" | head -1)"
    if [ -n "$wpid" ] && alive "$wpid"; then
      in_scope jobs || continue
      line="$(ps -o pcpu=,etime= -p "${cpid:-$wpid}" 2>/dev/null | head -1)"
      pcpu="$(printf '%s' "$line" | awk '{print int($1)}')"
      et="$(etime_s "$(printf '%s' "$line" | awk '{print $2}')")"
      say "  running   $id $jname wrapper=$wpid child=${cpid:-?} cpu=${pcpu:-?}% up=${et:-?}s"
      if [ -n "${pcpu:-}" ] && [ "$pcpu" -gt "$RUNAWAY_CPU" ] && [ "${et:-0}" -gt "$RUNAWAY_SECONDS" ]; then
        stop_pid "$wpid" "runaway: ${pcpu}% CPU for $((et / 60)) min; the wrapper's cleanup stops the whole job"
      elif [ "$include_idle" = 1 ] && [ -n "$cpid" ] && [ "${et:-0}" -gt 600 ]; then
        c1="$(cpu_s "$(ps -o cputime= -p "$cpid" 2>/dev/null | tr -d ' ')")"
        sleep "$IDLE_SAMPLE"
        c2="$(cpu_s "$(ps -o cputime= -p "$cpid" 2>/dev/null | tr -d ' ')")"
        if [ -n "$c1" ] && [ "$c1" = "$c2" ]; then stop_pid "$wpid" "idle: no CPU progress in ${IDLE_SAMPLE}s"; fi
      fi
    else
      in_scope records || continue
      say "  dead      $id $jname: wrapper pid ${wpid:-?} is gone but the record says running"
      if [ -n "$cpid" ] && alive "$cpid" && [ "$(stat_of "$cpid")" != "Z" ]; then
        first="$(sed -n 's/.*"cmd": "\([^" ]*\).*/\1/p' "$f" | head -1)"
        case "$(args_of "$cpid")" in
          *"$(basename "${first:-__none__}")"*) stop_pid "$cpid" "orphaned child of a dead gs_run wrapper" ;;
        esac
      fi
      if [ "$yes" = 1 ]; then mark_record "$f" lost; say "    record marked lost"; else say "    would mark the record lost"; fi
    fi
  done
  [ "$found" = 1 ] || say "  none running"
fi

if in_scope zombies; then
  say "zombies:"
  zlist="$(ps -axo pid=,ppid=,stat= 2>/dev/null | awk '$3 ~ /^Z/ {print $1 " " $2}')"
  if [ -z "$zlist" ]; then
    say "  none"
  else
    printf '%s\n' "$zlist" | while read -r zpid zppid; do
      say "  zombie $zpid ($(ps -o comm= -p "$zpid" 2>/dev/null | head -1)) parent $zppid: $(args_of "$zppid")"
      if protected_parent "$zppid"; then
        say "    parent is protected or init; not signalled (init reaps it, or reboot)"
      elif [ "$zombie_parents" = 1 ]; then
        stop_pid "$zppid" "parent of zombie $zpid"
      else
        say "    (a zombie cannot be killed; add --zombie-parents --yes to TERM its parent $zppid)"
      fi
    done
  fi
fi

if in_scope lock; then
  owner="$GPU_LOCK.owner"
  if [ -f "$owner" ]; then
    opid="$(awk '{print $1}' "$owner" | head -1)"
    if [ -n "$opid" ] && alive "$opid"; then
      say "GPU lock: held by pid $opid ($(cut -c1-80 "$owner"))"
    else
      say "GPU lock: owner record points at dead pid ${opid:-?}"
      if [ "$yes" = 1 ]; then rm -f "$owner"; say "  removed $owner"; else say "  would remove $owner"; fi
    fi
  else
    say "GPU lock: free"
  fi
fi

if in_scope pids && [ "${#pids[@]}" -gt 0 ]; then
  say "explicit pids:"
  for p in "${pids[@]}"; do
    case "$p" in ''|*[!0-9]*) say "  skipping non-numeric pid '$p'"; continue ;; esac
    if [ "$p" -le 1 ] || [ "$p" = "$$" ] || [ "$p" = "$PPID" ]; then say "  refusing pid $p (init, this script or its parent)"; continue; fi
    if ! alive "$p"; then say "  pid $p is not running"; continue; fi
    stop_pid "$p" "named with --pid"
  done
fi
exit 0
