#!/usr/bin/env bash
# One-screen health report for the three machines (this Mac, iBuyPower, DGX Spark).
#
#   scripts/fleet_status.sh                  all hosts in scripts/fleet/hosts.conf
#   scripts/fleet_status.sh --local          only this machine, no ssh
#   scripts/fleet_status.sh --host spark     one host
#   scripts/fleet_status.sh --json           machine-readable
#   scripts/fleet_status.sh --raw            print the raw probe output per host
#   scripts/fleet_status.sh --sample 0       skip the 10 s working-versus-spinning CPU/IO sample
#   scripts/fleet_status.sh --no-gate        skip the Spark demo-gate lines (GPU lock, memory gate, labs, queue)
#   FLEET_HOST_KALEL=192.168.1.119 scripts/fleet_status.sh    override an address (DHCP moved it)
#
# For every busy process it also shows the owner: tmux session, git worktree and branch, systemd
# unit, parent chain, listening port with its connected clients, and the device environment.
# Read-only: it runs scripts/fleet/probe.sh over ssh (BatchMode, key login only) and suggests
# fixes as text. It never runs them. Exit code: 0 all ok, 1 warnings, 2 critical or unreachable.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOSTS_FILE="${FLEET_HOSTS_FILE:-$ROOT/scripts/fleet/hosts.conf}"
BUDGETS_FILE="${FLEET_BUDGETS_FILE:-$ROOT/scripts/fleet/budgets.conf}"
PROBE="$ROOT/scripts/fleet/probe.sh"
SSH_TIMEOUT="${FLEET_SSH_TIMEOUT:-6}"
# A unix socket path must stay under ~104 bytes on macOS; $TMPDIR (/var/folders/...) is far too long, so use /tmp.
CTL_DIR="/tmp/gsf-$(id -u)"
mkdir -p "$CTL_DIR" && chmod 700 "$CTL_DIR"

only_host=""; local_only=0; as_json=0; raw=0; quiet=0; gate=1
while [ $# -gt 0 ]; do
  case "$1" in
    --local) local_only=1 ;;
    --host) only_host="${2:?--host needs a name}"; shift ;;
    --json) as_json=1 ;;
    --raw) raw=1 ;;
    --quiet) quiet=1 ;;
    --no-gate) gate=0 ;;
    --sample) FLEET_SAMPLE_SECONDS="${2:?--sample needs seconds (0 = no sample)}"; shift ;;
    -h|--help) sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 64 ;;
  esac
  shift
done

work="$(mktemp -d "${TMPDIR:-/tmp}/gs-fleet.XXXXXX")"
trap 'rm -rf "$work"' EXIT

SAMPLE_SECONDS="${FLEET_SAMPLE_SECONDS:-10}"

ssh_probe() {  # user addr errfile -> report on stdout, nonzero if ssh failed
  local user="$1" addr="$2" errfile="$3"
  ssh -o BatchMode=yes -o ConnectTimeout="$SSH_TIMEOUT" -o StrictHostKeyChecking=accept-new \
      -o ControlMaster=auto -o ControlPersist=60 -o "ControlPath=$CTL_DIR/%C" \
      -o ServerAliveInterval=5 -o ServerAliveCountMax=2 \
      "${user}@${addr}" "FLEET_SAMPLE_SECONDS=$SAMPLE_SECONDS bash -s" < "$PROBE" 2>"$errfile"
}

probe_host() {  # name user host fallbacks
  local name="$1" user="$2" host="$3" fallbacks="${4:-}"
  local upper envvar addr out errfile="$work/$name.err"
  upper="$(printf '%s' "$name" | tr 'a-z-' 'A-Z_')"
  envvar="FLEET_HOST_${upper}"
  addr="${!envvar:-$host}"
  if [ "$addr" = "local" ]; then
    FLEET_SAMPLE_SECONDS="$SAMPLE_SECONDS" bash "$PROBE"
    return
  fi
  local candidates=("$addr")
  IFS=',' read -r -a more <<< "$fallbacks"
  for f in "${more[@]:-}"; do [ -n "$f" ] && candidates+=("$f"); done
  for c in "${candidates[@]}"; do
    if out="$(ssh_probe "$user" "$c" "$errfile")" && printf '%s' "$out" | head -1 | grep -q '^FLEET_PROBE'; then
      printf '%s\n' "$out"
      return
    fi
  done
  local why
  why="$(tr '\n' ' ' < "$errfile" 2>/dev/null | cut -c1-120)"
  echo "FLEET_UNREACHABLE ${why:-no answer from ${candidates[*]}}"
}

# Each host is probed in parallel: the probe takes a short CPU/IO sample (SAMPLE_SECONDS) to tell a
# busy server from a spinning process, and three of those in a row would take half a minute.
args=()
names=()
count=0
while read -r name user host fallbacks; do
  case "$name" in ''|\#*) continue ;; esac
  [ -n "$only_host" ] && [ "$name" != "$only_host" ] && continue
  if [ "$local_only" = 1 ] && [ "$host" != "local" ]; then continue; fi
  ( probe_host "$name" "$user" "$host" "${fallbacks:-}" > "$work/$name.report" ) &
  names+=("$name")
  args+=("$name=$work/$name.report")
  count=$((count + 1))
done < "$HOSTS_FILE"
wait

if [ "$count" = 0 ]; then
  echo "no matching host in $HOSTS_FILE" >&2
  exit 64
fi
if [ "$raw" = 1 ]; then
  for name in "${names[@]}"; do echo "=== $name"; cat "$work/$name.report"; done
  exit 0
fi

fmt=()
[ "$as_json" = 1 ] && fmt=(--json)
# A checkout without installed dependencies (a fresh worktree, ~/code/gs-main on the Spark) cannot import aoep_shared
# (pydantic). Use FLEET_PYTHON, else python3 when it can, else the shared venv of the main checkout.
PYBIN="${FLEET_PYTHON:-python3}"
if [ -z "${FLEET_PYTHON:-}" ] && ! "$PYBIN" -c 'import pydantic' >/dev/null 2>&1; then
  for cand in "${AOEP_VENV:-$HOME/code/getschoolled/.venv}/bin/python" "$HOME/getschoolled/.venv/bin/python"; do
    [ -x "$cand" ] && { PYBIN="$cand"; break; }
  done
fi
PYTHONPATH="$ROOT/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYBIN" -m aoep_shared.fleet_status render --budgets "$BUDGETS_FILE" ${fmt[@]+"${fmt[@]}"} "${args[@]}"
rc=$?
# The Spark's demo gate: four plain lines (GPU lock holder, memory vs the 16 GB gate, lab ports, queued waiters).
if [ "$gate" = 1 ] && [ "$as_json" = 0 ]; then
  gate_script="$ROOT/scripts/fleet/spark_gate.sh"
  while read -r gname guser ghost _rest; do
    case "$gname" in ''|\#*) continue ;; esac
    [ "$gname" = "spark" ] || continue
    [ -n "$only_host" ] && [ "$only_host" != "spark" ] && continue
    [ "$local_only" = 1 ] && [ "$ghost" != "local" ] && continue
    grep -q '^FLEET_UNREACHABLE' "$work/spark.report" 2>/dev/null && continue
    echo
    echo "Spark demo gate"
    envvar="FLEET_HOST_SPARK"; gaddr="${!envvar:-$ghost}"
    if [ "$gaddr" = "local" ]; then
      bash "$gate_script"
    else
      ssh -o BatchMode=yes -o ConnectTimeout="$SSH_TIMEOUT" -o ControlMaster=auto -o ControlPersist=60 -o "ControlPath=$CTL_DIR/%C" \
        "${guser}@${gaddr}" 'bash -s' < "$gate_script" 2>/dev/null || echo "  (could not reach ${gaddr} for the gate lines)"
    fi
  done < "$HOSTS_FILE"
  # Run on the Spark itself with --local: hosts.conf names it by address, so look at this machine directly.
  if [ "$local_only" = 1 ] && [ "$(uname -s)" = "Linux" ] && [ -z "$only_host" ]; then
    echo; echo "Spark demo gate (this machine)"; bash "$gate_script"
  fi
fi
[ "$quiet" = 1 ] && [ "$rc" = 0 ] && exit 0
exit "$rc"
