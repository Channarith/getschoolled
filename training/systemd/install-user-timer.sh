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

for name in aoep-spark-train.service aoep-spark-train.timer; do
  sed "s|@REPO@|$REPO|g" "$UNIT_SRC/$name" > "$UNIT_DIR/$name"
  echo "installed $UNIT_DIR/$name"
done

systemctl --user daemon-reload
echo "daemon-reload done. Timer is not started."

if [[ "$ENABLE" -eq 1 ]]; then
  systemctl --user enable --now aoep-spark-train.timer
  systemctl --user status aoep-spark-train.timer --no-pager || true
else
  echo "Left disabled. To arm it:"
  echo "  systemctl --user enable --now aoep-spark-train.timer"
fi
