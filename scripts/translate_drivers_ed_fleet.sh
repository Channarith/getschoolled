#!/usr/bin/env bash
# Driver's ed demo translation across this Mac, the Spark, and the iBuyPower.
#
# The demo spoke English in Spanish and French because only Khmer had a written
# overlay. This job writes data/cert_machine/<lang>.json. Course Studio speaks a
# slide once its title, body, and spoken line are in that file. Khmer is left
# alone (it is already curated). Safe to stop and run again: finished lines are
# skipped.
#
# Does not stop the Spark's catalog translator on port 8002. The Spark share
# uses the free GPU under a different job name.
#
# Run this on the Mac:
#   bash scripts/translate_drivers_ed_fleet.sh start
#   bash scripts/translate_drivers_ed_fleet.sh start spark   # one machine only
#   bash scripts/translate_drivers_ed_fleet.sh status
#   bash scripts/translate_drivers_ed_fleet.sh collect
#
# Shares (no language is on two machines):
#   mac     es fr
#   spark   de it pt nl pl ru uk tr ar he hi bn ur fa zh ja ko vi
#   kalel   th id sw el cs          (NLLB_PROFILE=8gb)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HOSTS="$ROOT/scripts/fleet/hosts.conf"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new)
PY="${ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

host_of() { # name -> "user host"
  local name="$1" key user host
  key="$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')"
  key="FLEET_HOST_${key}"
  user="$(awk -v n="$name" '$1==n {print $2}' "$HOSTS")"
  host="$(awk -v n="$name" '$1==n {print $3}' "$HOSTS")"
  if [ -n "${!key:-}" ]; then
    host="${!key}"
  fi
  printf '%s %s\n' "$user" "$host"
}

start_one() { # share user host
  local share="$1" user="$2" host="$3" dest root
  dest="${user}@${host}"
  echo "== $share ($dest) =="
  if ! root="$("${SSH[@]}" "$dest" 'bash -s' << 'EOF'
for d in "$HOME/code/gs-wt/spark-eval-gates" "$HOME/code/getschoolled" "$HOME/getschoolled" "$HOME/code/gs-wt/main-current"; do
  if [ -x "$d/scripts/gs_run.sh" ]; then printf '%s\n' "$d"; exit 0; fi
done
exit 1
EOF
)"; then
    echo "$share: no checkout with scripts/gs_run.sh. Copy the repo there, then rerun." >&2
    return 1
  fi
  root="${root//$'\r'/}"
  echo "$share checkout: $root"
  "${SSH[@]}" "$dest" "mkdir -p '$root/scripts' '$root/data/cert_machine' '$root/output'"
  rsync -a "$ROOT/scripts/translate_drivers_ed.py" "$ROOT/scripts/translate_drivers_ed.sh" "$dest:$root/scripts/"
  rsync -a "$ROOT/data/cert_machine/_english.json" "$dest:$root/data/cert_machine/_english.json"
  "${SSH[@]}" "$dest" "cd '$root' && nohup bash scripts/translate_drivers_ed.sh '$share' >> output/drivers-ed-${share}.log 2>&1 < /dev/null & echo pid=\$!"
  echo "$share log: $root/output/drivers-ed-${share}.log"
}

cmd="${1:-start}"
case "$cmd" in
  start)
    want="${2:-all}"
    case "$want" in all|mac|spark|kalel) ;; *) echo "usage: start [all|mac|spark|kalel]" >&2; exit 2 ;; esac
    "$PY" "$ROOT/scripts/translate_drivers_ed.py" --plan
    mkdir -p "$ROOT/output" "$ROOT/data/cert_machine"
    if [ "$want" = all ] || [ "$want" = mac ]; then
      echo "== mac (this machine: es fr) =="
      nohup bash "$ROOT/scripts/translate_drivers_ed.sh" mac >> "$ROOT/output/drivers-ed-mac.log" 2>&1 &
      echo "mac pid $!  log output/drivers-ed-mac.log"
    fi
    if [ "$want" = all ] || [ "$want" = spark ]; then
      spark="$(host_of spark)"
      # shellcheck disable=SC2086
      start_one spark $spark || true
    fi
    if [ "$want" = all ] || [ "$want" = kalel ]; then
      kalel="$(host_of kalel)"
      # shellcheck disable=SC2086
      start_one kalel $kalel || true
    fi
    echo
    echo "Spanish and French land in data/cert_machine on this Mac."
    echo "Run: bash scripts/translate_drivers_ed_fleet.sh collect"
    echo "Then restart Course Studio (the one on port 8040 is still the old loader) and pick the language again."
    ;;
  status)
    "$PY" "$ROOT/scripts/translate_drivers_ed.py" --status || true
    echo "-- mac log --"
    tail -n 8 "$ROOT/output/drivers-ed-mac.log" 2>/dev/null || echo "(no local log yet)"
    for share in spark kalel; do
      spec="$(host_of "$share")"
      # shellcheck disable=SC2086
      set -- $spec
      echo "-- $share log --"
      "${SSH[@]}" "$1@$2" 'bash -s' "$share" << 'EOF' || echo "$share unreachable"
share="$1"
for d in "$HOME/code/gs-wt/spark-eval-gates" "$HOME/code/getschoolled" "$HOME/getschoolled" "$HOME/code/gs-wt/main-current"; do
  if [ -f "$d/output/drivers-ed-${share}.log" ]; then tail -n 8 "$d/output/drivers-ed-${share}.log"; exit 0; fi
done
echo "(no log yet)"
EOF
    done
    ;;
  collect)
    mkdir -p "$ROOT/data/cert_machine"
    for share in spark kalel; do
      spec="$(host_of "$share")"
      # shellcheck disable=SC2086
      set -- $spec
      dest="$1@$2"
      root="$("${SSH[@]}" "$dest" 'bash -s' << 'EOF' || true
for d in "$HOME/code/gs-wt/spark-eval-gates" "$HOME/code/getschoolled" "$HOME/getschoolled" "$HOME/code/gs-wt/main-current"; do
  if [ -d "$d/data/cert_machine" ]; then printf '%s\n' "$d"; exit 0; fi
done
exit 1
EOF
)"
      root="${root//$'\r'/}"
      if [ -z "$root" ]; then
        echo "$share: nothing to collect" >&2
        continue
      fi
      echo "collect $share from $root"
      rsync -a --exclude '_english.json' "$dest:$root/data/cert_machine/" "$ROOT/data/cert_machine/"
    done
    "$PY" "$ROOT/scripts/translate_drivers_ed.py" --status
    ;;
  *)
    echo "usage: translate_drivers_ed_fleet.sh start [all|mac|spark|kalel]|status|collect" >&2
    exit 2
    ;;
esac
