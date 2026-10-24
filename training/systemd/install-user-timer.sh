#!/usr/bin/env bash
# Install the nightly STEM training timer as a *user* systemd unit.
#
# This copies the unit files into ~/.config/systemd/user and enables the
# timer. It does not start a training run.
#
# Do not run this until you want the nightly job installed. Enabling is a
# separate step you opt into with --enable.
#
#   ./training/systemd/install-user-timer.sh           # install units only
#   ./training/systemd/install-user-timer.sh --enable  # also enable the timer
#
set -euo pipefail

ENABLE=0
if [[ "${1:-}" == "--enable" ]]; then
  ENABLE=1
elif [[ -n "${1:-}" ]]; then
  echo "usage: $0 [--enable]" >&2
  exit 2
fi

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_SRC="$REPO/training/systemd"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR"

# Size the unit's ceilings for THIS machine: keep the host reserve free (16 GB / 2 cores on the Spark,
# 6 GB / 2 cores elsewhere). Override with GS_RESERVE_GB / GS_RESERVE_CORES.
TOTAL_GB="$(awk '/^MemTotal:/{printf "%d", $2/1048576}' /proc/meminfo)"
CORES="$(nproc)"
if [[ "$(hostname | tr 'A-Z' 'a-z')" == *spark* || "$TOTAL_GB" -ge 100 ]]; then
  RESERVE_GB="${GS_RESERVE_GB:-16}"
else
  RESERVE_GB="${GS_RESERVE_GB:-6}"
fi
RESERVE_CORES="${GS_RESERVE_CORES:-2}"
MEMMAX="$(( TOTAL_GB - RESERVE_GB ))G"
CPUQUOTA="$(( (CORES - RESERVE_CORES) * 100 ))%"
echo "limits for this machine: MemoryMax=$MEMMAX CPUQuota=$CPUQUOTA (reserve ${RESERVE_GB}G, ${RESERVE_CORES} cores)"

for name in aoep-spark-train.service aoep-spark-train.timer; do
  sed -e "s|@REPO@|$REPO|g" -e "s|@MEMMAX@|$MEMMAX|g" -e "s|@CPUQUOTA@|$CPUQUOTA|g" \
    "$UNIT_SRC/$name" > "$UNIT_DIR/$name"
  echo "installed $UNIT_DIR/$name"
done
if command -v systemd-analyze >/dev/null 2>&1; then
  systemd-analyze --user verify "$UNIT_DIR/aoep-spark-train.service" || echo "WARNING: unit verify reported problems (see above)"
fi

systemctl --user daemon-reload
echo "daemon-reload done. Timer is not started."

if [[ "$ENABLE" -eq 1 ]]; then
  systemctl --user enable --now aoep-spark-train.timer
  systemctl --user status aoep-spark-train.timer --no-pager || true
else
  echo "Left disabled. To arm it:"
  echo "  systemctl --user enable --now aoep-spark-train.timer"
fi
