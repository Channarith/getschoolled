#!/usr/bin/env bash
# Install the fleet systemd user units for THIS machine, with limits from budgets.conf.
#
#   scripts/fleet/install-units.sh                 install units (nothing is started)
#   scripts/fleet/install-units.sh --enable        also enable gs-fleet-check.timer
#   scripts/fleet/install-units.sh --dest DIR      write somewhere else and do not call systemctl (tests)
#
# Nothing here needs root. Units go to ~/.config/systemd/user.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC="$ROOT/scripts/fleet/systemd"
dest="$HOME/.config/systemd/user"
enable=0; call_systemctl=1
while [ $# -gt 0 ]; do
  case "$1" in
    --enable) enable=1 ;;
    --dest) dest="${2:?--dest needs a folder}"; call_systemctl=0; shift ;;
    -h|--help) sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "install-units: unknown option $1" >&2; exit 64 ;;
  esac
  shift
done

plan="$("$ROOT/scripts/gs_run.sh" --dry-run -- true)" || { echo "install-units: gs_run --dry-run failed" >&2; exit 1; }
field() { printf '%s\n' "$plan" | sed -n "s/.*$1: *\([0-9]*\).*/\1/p" | head -1; }
mem_max="$(field mem_max_gb)"; mem_high="$(field mem_high_gb)"; cpu_quota="$(field cpu_quota)"
nice_n="$(field nice)"; io_weight="$(field io_weight)"; tasks_max="$(field tasks_max)"
[ -n "$mem_max" ] && [ -n "$cpu_quota" ] || { echo "install-units: could not read limits from gs_run --dry-run" >&2; exit 1; }

mkdir -p "$dest"
[ "$call_systemctl" = 1 ] && mkdir -p "$HOME/.config/gs"
for f in gs-batch.slice gs-job@.service gs-fleet-check.service gs-fleet-check.timer; do
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
  echo "done. Check:  systemctl --user list-timers | grep gs-"
fi
