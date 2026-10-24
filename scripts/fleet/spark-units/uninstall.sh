#!/usr/bin/env bash
# Remove Spark systemd USER units installed by install.sh. DRY RUN BY DEFAULT.
#
#   scripts/fleet/spark-units/uninstall.sh                          # what would go: the two lab units
#   scripts/fleet/spark-units/uninstall.sh --apply                  # stop, disable and remove them
#   scripts/fleet/spark-units/uninstall.sh --apply aoep-enroll-ui   # only the named unit(s)
#
# Default targets are the enrollment page and the listening lab. Training, ingest and the balance monitor are
# never touched unless you name them. Every unit file removed is first copied to STATE/backup-<time>/.
# Environment (tests): SU_UNITS_DIR  SU_STATE_DIR  SYSTEMCTL (default "systemctl --user")
set -uo pipefail
UNITS_DIR="${SU_UNITS_DIR:-${HOME}/.config/systemd/user}"
STATE="${SU_STATE_DIR:-${HOME}/.local/share/aoep-train}"
SYSTEMCTL="${SYSTEMCTL:-systemctl --user}"
APPLY=0; NAMES=()
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    -h|--help) sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "uninstall.sh: unknown option $a" >&2; exit 64 ;;
    *) NAMES+=("${a%.service}") ;;
  esac
done
[ "${#NAMES[@]}" -gt 0 ] || NAMES=(aoep-enroll-ui aoep-listening-lab)
BACKUP="${STATE}/backup-$(date +%Y%m%d-%H%M%S)"
n=0
for u in "${NAMES[@]}"; do
  f="${UNITS_DIR}/${u}.service"
  if [ ! -e "${f}" ]; then echo "  absent   ${u}.service"; continue; fi
  n=$((n + 1))
  if [ "${APPLY}" = 0 ]; then echo "  WOULD REMOVE ${u}.service"; continue; fi
  mkdir -p "${BACKUP}" && cp -a "${f}" "${BACKUP}/"
  ${SYSTEMCTL} stop "${u}.service" >/dev/null 2>&1
  ${SYSTEMCTL} disable "${u}.service" >/dev/null 2>&1
  rm -f "${f}"; echo "  removed  ${u}.service (backup in ${BACKUP})"
done
if [ "${APPLY}" = 1 ] && [ "${n}" -gt 0 ]; then ${SYSTEMCTL} daemon-reload; fi
[ "${APPLY}" = 0 ] && echo "DRY RUN: ${n} unit(s) would be removed. Re-run with --apply."
exit 0
