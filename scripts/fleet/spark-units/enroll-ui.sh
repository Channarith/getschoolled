#!/usr/bin/env bash
# Launcher for the voice enrollment page (consent + recording). Binds 127.0.0.1:8780 only; reach it with
#   ssh -L 8780:127.0.0.1:8780 nvidia@<spark>   then   http://localhost:8780/
# Recordings and consent files stay under AOEP_VOICES_DIR (default ~/voices) and never leave the machine.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AOEP_ENROLL_ROOT:-$(cd "${HERE}/../../.." && pwd)}"
VENV="${AOEP_VENV:-${HOME}/code/getschoolled/.venv}"
PY="${VENV}/bin/python"; [ -x "${PY}" ] || PY="$(command -v python3)"
VOICES="${AOEP_VOICES_DIR:-${HOME}/voices}"
PORT="${AOEP_ENROLL_PORT:-8780}"
mkdir -p "${VOICES}"
cd "${ROOT}" || exit 1
export PYTHONPATH="${ROOT}:${ROOT}/packages/shared/src${PYTHONPATH:+:${PYTHONPATH}}"
exec "${PY}" -m tts_bakeoff.voice_clone.enroll_ui --root "${VOICES}" --port "${PORT}"
