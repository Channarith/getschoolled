#!/usr/bin/env bash
# Install the fleet systemd user units for THIS machine, with limits from budgets.conf.
#
#   scripts/fleet/install-units.sh                       install units (nothing is started)
#   scripts/fleet/install-units.sh --enable              also enable gs-fleet-check.timer (health log every 10 min)
#   scripts/fleet/install-units.sh --enable-worker       also enable linger, start gs-worker, the hourly revive
#                                                        timer and the daily summary timer
#   scripts/fleet/install-units.sh --disable-type TYPE   (repeatable, with --enable-worker) keep a job type off
#                                                        on this machine, e.g. translate-stage while another
#                                                        session is already doing it
#   scripts/fleet/install-units.sh --uninstall           stop and remove everything this script installed
#                                                        (jobs already queued stay in ~/.gs-queue/queue.db)
#   scripts/fleet/install-units.sh --dest DIR            write somewhere else and do not call systemctl (tests)
#
# Run it from the checkout the worker should run from (on the Spark: a git worktree of origin/main, never
# the main checkout, which sits on a feature branch). The units point at THIS checkout.
# Nothing here needs root. Units go to ~/.config/systemd/user.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/scripts/fleet/systemd"
dest="$HOME/.config/systemd/user"
enable=0; enable_worker=0; uninstall=0; call_systemctl=1
disable_types=()
UNITS="gs-batch.slice gs-job@.service gs-fleet-check.service gs-fleet-check.timer gs-worker.service gs-worker-revive.service gs-worker-revive.timer gs-queue-daily.service gs-queue-daily.timer"
while [ $# -gt 0 ]; do
  case "$1" in
    --enable) enable=1 ;;
    --enable-worker) enable_worker=1 ;;
    --disable-type) disable_types+=("${2:?--disable-type needs a job type}"); shift ;;
    --uninstall) uninstall=1 ;;
    --dest) dest="${2:?--dest needs a folder}"; call_systemctl=0; shift ;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "install-units: unknown option $1" >&2; exit 64 ;;
  esac
  shift
done

if [ "$uninstall" = 1 ]; then
  if [ "$call_systemctl" = 1 ]; then
    for u in gs-worker-revive.timer gs-queue-daily.timer gs-fleet-check.timer gs-worker.service; do
      systemctl --user disable --now "$u" 2>/dev/null || true
    done
  fi
  for f in $UNITS; do rm -f "$dest/$f" && echo "removed $dest/$f"; done
  [ "$call_systemctl" = 1 ] && systemctl --user daemon-reload
  echo "uninstalled. The queue (~/.gs-queue) was left alone; delete it by hand if you want a clean slate."
  exit 0
fi

plan="$("$ROOT/scripts/gs_run.sh" --dry-run -- true)" || { echo "install-units: gs_run --dry-run failed" >&2; exit 1; }
field() { printf '%s\n' "$plan" | sed -n "s/.*$1: *\([0-9]*\).*/\1/p" | head -1; }
mem_max="$(field mem_max_gb)"; mem_high="$(field mem_high_gb)"; cpu_quota="$(field cpu_quota)"
nice_n="$(field nice)"; io_weight="$(field io_weight)"; tasks_max="$(field tasks_max)"
[ -n "$mem_max" ] && [ -n "$cpu_quota" ] || { echo "install-units: could not read limits from gs_run --dry-run" >&2; exit 1; }

mkdir -p "$dest"
[ "$call_systemctl" = 1 ] && mkdir -p "$HOME/.config/gs"
for f in $UNITS; do
  sed -e "s#@REPO@#$ROOT#g" -e "s#@MEM_MAX@#${mem_max}G#g" -e "s#@MEM_HIGH@#${mem_high}G#g" \
      -e "s#@CPU_QUOTA@#${cpu_quota}%#g" -e "s#@TASKS_MAX@#${tasks_max:-4096}#g" -e "s#@IO_WEIGHT@#${io_weight:-50}#g" \
      "$SRC/$f" > "$dest/$f"
  echo "installed $dest/$f"
done
if [ "$call_systemctl" = 1 ] && [ ! -f "$HOME/.config/gs/example.env" ]; then cp "$SRC/example.env" "$HOME/.config/gs/example.env"; fi
if grep -l '@[A-Z_]*@' "$dest"/gs-* >/dev/null 2>&1; then echo "install-units: unreplaced placeholder left in $dest" >&2; exit 1; fi

if [ "$call_systemctl" = 1 ]; then
  systemctl --user daemon-reload
  if [ "$enable" = 1 ]; then systemctl --user enable --now gs-fleet-check.timer; fi
  if [ "$enable_worker" = 1 ]; then
    "$ROOT/scripts/fleet/boot_check.sh" || { echo "install-units: boot_check reported a FAIL; fix it first (worker not started)" >&2; exit 1; }
    if ! loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q "Linger=yes"; then
      loginctl enable-linger "$(id -un)" 2>/dev/null && echo "enabled linger" \
        || echo "WARN: could not enable linger; run once by hand: sudo loginctl enable-linger $(id -un)"
    fi
    [ -f "$HOME/.config/gs/worker.env" ] || printf '# Environment for gs-worker (and the jobs it starts). Example:\n#BASE_MODEL=/home/nvidia/code/getschoolled/models/weights/qwen2.5-7b-instruct\n#HARVEST_SEEDS=%s/.config/gs/harvest-seeds.jsonl\n' "$HOME" > "$HOME/.config/gs/worker.env"
    for t in "${disable_types[@]+"${disable_types[@]}"}"; do
      "$ROOT/scripts/gs_worker.sh" disable "$t" || echo "WARN: could not disable $t"
    done
    systemctl --user enable --now gs-worker.service gs-worker-revive.timer gs-queue-daily.timer
    echo "worker started. Check:  scripts/gs_worker.sh status   and   systemctl --user status gs-worker"
  fi
  echo "done. Check:  systemctl --user list-timers | grep gs-"
fi
