#!/usr/bin/env bash
# Launcher for the voice listening lab. Binds 127.0.0.1:8790 only; reach it with
#   ssh -L 8790:127.0.0.1:8790 nvidia@<spark>   then   http://localhost:8790/
# It serves AOEP_LAB_OUT, else the newest <root>/runs/*-clones folder (the voice-clone bake-off output), else an
# empty lab (load folders from the page). The unit restarts it, so a new run is picked up after a restart.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AOEP_LAB_ROOT:-$(cd "${HERE}/../../.." && pwd)}"
VENV="${AOEP_VENV:-${HOME}/code/getschoolled/.venv}"
PY="${VENV}/bin/python"; [ -x "${PY}" ] || PY="$(command -v python3)"
PORT="${AOEP_LAB_PORT:-8790}"
OUT="${AOEP_LAB_OUT:-}"
if [ -z "${OUT}" ]; then
  OUT="$(find "${ROOT}/runs" "${HOME}/code/gs-main/runs" -maxdepth 1 -type d -name '*-clones' 2>/dev/null | sort | tail -n 1)"
fi
cd "${ROOT}" || exit 1
export PYTHONPATH="${ROOT}:${ROOT}/packages/shared/src${PYTHONPATH:+:${PYTHONPATH}}"
args=(--port "${PORT}" --no-open)
[ -n "${OUT}" ] && [ -d "${OUT}" ] && args+=(--out "${OUT}")
echo "listening lab: root=${ROOT} out=${OUT:-none} port=${PORT}"
exec "${PY}" -m tts_bakeoff.lab "${args[@]}"
