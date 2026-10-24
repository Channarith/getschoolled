#!/usr/bin/env bash
# Boot/start sanity check for the fleet worker. Run by gs-worker.service (ExecStartPre) and by hand:
#   scripts/fleet/boot_check.sh
# Prints PASS / WARN / FAIL lines. Exit 1 only for a FAIL (the worker cannot work at all); WARNs are
# things to fix but the worker still starts (it will refuse GPU jobs itself if CUDA is broken).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fail=0
ok()   { echo "PASS  $*"; }
warn() { echo "WARN  $*"; }
bad()  { echo "FAIL  $*"; fail=1; }

PY="${GS_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in "$ROOT/.venv/bin/python" "$HOME/code/getschoolled/.venv/bin/python" "$HOME/getschoolled/.venv/bin/python"; do
    [ -x "$c" ] && PY="$c" && break
  done
fi
PY="${PY:-python3}"

command -v "$PY" >/dev/null 2>&1 && ok "python: $PY ($("$PY" -c 'import sys;print(sys.version.split()[0])' 2>/dev/null))" || bad "python not found ($PY)"
[ -x "$ROOT/scripts/gs_run.sh" ] && ok "gs_run.sh present" || bad "scripts/gs_run.sh missing or not executable in $ROOT"
PYTHONPATH="$ROOT/packages/shared/src" "$PY" "$ROOT/scripts/fleet/queue.py" validate >/dev/null 2>&1 && ok "job manifests valid" || bad "job manifests invalid: run scripts/fleet/queue.py validate"

state="${GS_STATE_DIR:-$HOME/.gs-queue}"
mkdir -p "$state/logs" 2>/dev/null && [ -w "$state" ] && ok "state dir writable: $state" || bad "cannot write $state"

avail_gb="$(df -Pk "$state" 2>/dev/null | awk 'NR==2 {printf "%d", $4/1048576}')"
if [ -n "$avail_gb" ] && [ "$avail_gb" -lt 20 ]; then warn "only ${avail_gb} GB free on the state disk"; else ok "disk free: ${avail_gb:-?} GB"; fi

if [ "$(uname -s)" = "Linux" ]; then
  if systemd-run --user --scope --quiet true 2>/dev/null; then ok "systemd-run --user --scope works (job limits will apply)"
  else warn "systemd-run --user --scope failed: jobs fall back to process-group limits only"; fi
  if loginctl show-user "$(id -un)" -p Linger 2>/dev/null | grep -q "Linger=yes"; then ok "linger enabled (worker survives logout and starts at boot)"
  else warn "linger is OFF: run  loginctl enable-linger $(id -un)  so the worker starts at boot without a login"; fi
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name --format=csv,noheader >/dev/null 2>&1 && ok "nvidia-smi sees a GPU" || warn "nvidia-smi present but failed (driver reload after a kernel update? reboot)"
  fi
fi
"$ROOT/scripts/gs_run.sh" --dry-run -- true >/dev/null 2>&1 && ok "gs_run --dry-run" || warn "gs_run --dry-run failed"
[ "$(date +%Y)" -ge 2026 ] && ok "clock looks sane ($(date +%F))" || warn "system clock looks wrong ($(date +%F)): job windows and leases depend on it"
exit "$fail"
