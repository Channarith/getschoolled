#!/usr/bin/env bash
# Install or refresh the Spark's systemd USER units from this repo.
#
# DRY RUN BY DEFAULT: prints, for every unit and drop-in, whether it is new / unchanged / changed (with a diff against
# the live file) and what it would retire. Nothing is written until --apply.
#
#   scripts/fleet/spark-units/install.sh                       # see what would change
#   scripts/fleet/spark-units/install.sh --apply               # write units (backs up the live ones first)
#   scripts/fleet/spark-units/install.sh --apply --restart aoep-gpu-balance
#
# Rules it keeps:
#   - idempotent: a second --apply changes nothing;
#   - never restarts a running service unless --restart NAME is given (a running service keeps running the OLD
#     definition until then; systemctl --user status shows "changed on disk");
#   - never enables or disables anything unless --enable NAME is given (the enabled/disabled state you have stays);
#   - backs up every live unit/drop-in it touches to STATE/backup-<time>/ and prints the exact rollback commands;
#   - the retired drop-in aoep-voice-ingest.service.d/gpu.conf (forced AOEP_ASR_DEVICE=cuda unconditionally) is
#     backed up and removed on --apply, because voice-ingest-forever.sh now decides that itself.
#
# Options: --apply  --root DIR (repo/worktree the units run from; default: the repo this script is in)
#          --restart NAME (repeatable)  --enable NAME (repeatable)  --with-legacy-translate  -h
# Environment (tests): SU_UNITS_DIR (default ~/.config/systemd/user)  SU_STATE_DIR (default ~/.local/share/aoep-train)
#                      SYSTEMCTL (default "systemctl --user")  SU_PY (python used for the import preflight)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../../.." && pwd)"
UNITS_DIR="${SU_UNITS_DIR:-${HOME}/.config/systemd/user}"
STATE="${SU_STATE_DIR:-${HOME}/.local/share/aoep-train}"
SYSTEMCTL="${SYSTEMCTL:-systemctl --user}"
APPLY=0; LEGACY=0
RESTART=(); ENABLE=()

usage() { sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --root) ROOT="$(cd "${2:?--root needs a directory}" && pwd)"; shift ;;
    --restart) RESTART+=("${2:?}"); shift ;;
    --enable) ENABLE+=("${2:?}"); shift ;;
    --with-legacy-translate) LEGACY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install.sh: unknown option $1" >&2; exit 64 ;;
  esac
  shift
done

UNITS=(aoep-llm-train aoep-voice-train aoep-voice-ingest aoep-gpu-balance aoep-enroll-ui aoep-listening-lab)
[ "${LEGACY}" = 1 ] && UNITS+=(aoep-course-translate)
RETIRED_DROPINS=("aoep-voice-ingest.service.d/gpu.conf")
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP="${STATE}/backup-${TS}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/spark-units.XXXXXX")"
trap 'rm -rf "${TMP}"' EXIT

say() { printf '%s\n' "$*"; }
render() { sed "s#@ROOT@#${ROOT}#g" "$1"; }

changed=0
declare_changed() { changed=$((changed + 1)); }
planned_files=()   # "src_rendered|dest|relname"
new_rels=()        # files that did not exist before (rollback = remove them)

plan_file() {   # plan_file RELNAME RENDERED_FILE
  local rel="$1" new="$2" dest="${UNITS_DIR}/$1"
  if [ ! -e "${dest}" ]; then
    say "  NEW      ${rel}"
    planned_files+=("${new}|${dest}|${rel}"); new_rels+=("${rel}"); declare_changed
  elif cmp -s "${new}" "${dest}"; then
    say "  same     ${rel}"
  else
    say "  CHANGED  ${rel}"
    diff -u "${dest}" "${new}" | sed '1,2d' | head -40 | sed 's/^/             /'
    planned_files+=("${new}|${dest}|${rel}"); declare_changed
  fi
}

say "Spark units: ${ROOT}"
say "live units dir: ${UNITS_DIR}   state dir: ${STATE}"
say ""
say "-- preflight --"
pf_fail=0
for f in "${HERE}"/*.sh; do
  if bash -n "${f}" 2>/dev/null; then say "  PASS  syntax $(basename "${f}")"; else say "  FAIL  syntax $(basename "${f}")"; pf_fail=1; fi
done
PYBIN="${SU_PY:-${AOEP_VENV:-${HOME}/code/getschoolled/.venv}/bin/python}"
[ -x "${PYBIN}" ] || PYBIN="$(command -v python3 || true)"
if [ -n "${PYBIN}" ] && PYTHONPATH="${ROOT}/packages/shared/src" "${PYBIN}" -c 'import aoep_shared.spark_balance, aoep_shared.gpu_lock' 2>/dev/null; then
  say "  PASS  monitor imports with ${PYBIN}"
else
  say "  FAIL  the monitor does not import from ${ROOT}/packages/shared/src (python: ${PYBIN:-none})"; pf_fail=1
fi
if [ "${pf_fail}" = 1 ] && [ "${APPLY}" = 1 ]; then say ""; say "preflight failed: nothing written."; exit 1; fi

say ""
say "-- units --"
for u in "${UNITS[@]}"; do
  src="${HERE}/units/${u}.service"
  [ -f "${src}" ] || { say "  MISSING template ${u}.service"; exit 1; }
  render "${src}" > "${TMP}/${u}.service"
  plan_file "${u}.service" "${TMP}/${u}.service"
  if [ -d "${HERE}/units/${u}.service.d" ]; then
    for d in "${HERE}/units/${u}.service.d"/*.conf; do
      [ -f "${d}" ] || continue
      mkdir -p "${TMP}/${u}.service.d"
      render "${d}" > "${TMP}/${u}.service.d/$(basename "${d}")"
      plan_file "${u}.service.d/$(basename "${d}")" "${TMP}/${u}.service.d/$(basename "${d}")"
    done
  fi
done

retire=()
for r in "${RETIRED_DROPINS[@]}"; do
  if [ -e "${UNITS_DIR}/${r}" ]; then
    say "  RETIRE   ${r}  (backed up, then removed on --apply)"
    retire+=("${r}"); declare_changed
  fi
done

say ""
if [ "${APPLY}" = 0 ]; then
  say "DRY RUN: ${changed} change(s) would be made. Nothing was written. Re-run with --apply to install."
  [ "${#RESTART[@]}" -gt 0 ] && say "(--restart ignored in a dry run)"
  exit 0
fi

if [ "${changed}" = 0 ]; then
  say "Nothing to change (already up to date)."
else
  mkdir -p "${BACKUP}"
  for entry in ${planned_files[@]+"${planned_files[@]}"}; do
    IFS='|' read -r _new dest rel <<<"${entry}"
    if [ -e "${dest}" ]; then
      mkdir -p "${BACKUP}/$(dirname "${rel}")"; cp -a "${dest}" "${BACKUP}/${rel}"
    fi
  done
  for r in ${retire[@]+"${retire[@]}"}; do
    mkdir -p "${BACKUP}/$(dirname "${r}")"; cp -a "${UNITS_DIR}/${r}" "${BACKUP}/${r}"
  done
  for entry in ${planned_files[@]+"${planned_files[@]}"}; do
    IFS='|' read -r new dest rel <<<"${entry}"
    mkdir -p "$(dirname "${dest}")"; cp "${new}" "${dest}"; say "  wrote    ${rel}"
  done
  for r in ${retire[@]+"${retire[@]}"}; do
    rm -f "${UNITS_DIR}/${r}"; rmdir "$(dirname "${UNITS_DIR}/${r}")" 2>/dev/null || true; say "  removed  ${r}"
  done
  ${SYSTEMCTL} daemon-reload
  say "  daemon-reload done"
fi

for n in ${ENABLE[@]+"${ENABLE[@]}"}; do
  n="${n%.service}"; ${SYSTEMCTL} enable "${n}.service" && say "  enabled  ${n}"
done
for n in ${RESTART[@]+"${RESTART[@]}"}; do
  n="${n%.service}"
  case "${n}" in
    aoep-llm-train) say "  WARNING  restarting ${n} stops the cycle that is running (a frozen SIGSTOP loop is released by systemd)" ;;
    aoep-voice-ingest) say "  WARNING  restarting ${n} abandons the channel being ingested (the queue resumes at the next one)" ;;
  esac
  ${SYSTEMCTL} restart "${n}.service" && say "  restarted ${n}"
done

say ""
if [ "${changed}" -gt 0 ]; then
  say "Running services keep the OLD definition until restarted. To apply one:"
  say "  ${SYSTEMCTL} restart aoep-gpu-balance.service      # safe: it only watches"
  say ""
  say "ROLLBACK (restore what was there, reload, restart what you restarted):"
  say "  cp -a ${BACKUP}/. ${UNITS_DIR}/ && ${SYSTEMCTL} daemon-reload"
  if [ "${#new_rels[@]}" -gt 0 ]; then
    say "  files that did not exist before (nothing to restore, remove them):"
    for rel in "${new_rels[@]}"; do say "    rm -f ${UNITS_DIR}/${rel}"; done
    say "  ${SYSTEMCTL} daemon-reload"
  fi
  say "  (the backup holds every file this run replaced or retired, in the same relative layout)"
fi
exit 0
