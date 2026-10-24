#!/usr/bin/env bash
# LEGACY (kept so the file that ran on the Spark is reviewable; do NOT enable its unit).
#
# This was the v1 course-translation loop: CPU only (NLLB_DEVICE=cpu), concurrency 1, skip-by-file-name. Skip-by-name
# keeps translations made from stale English, and CPU NLLB is about 15x slower than CUDA. It is replaced by
# scripts/translate_catalog_v2.py (source-hash aware, GPU, validated), run through scripts/gs_run.sh --gpu.
#
# Safety: it refuses to run unless AOEP_LEGACY_TRANSLATE=1, so an accidental `systemctl --user enable --now` does
# nothing. The user stopped and disabled aoep-course-translate.service on 2026-10-24.
set -u
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

if [ "${AOEP_LEGACY_TRANSLATE:-0}" != "1" ]; then
  su_log "legacy translate loop is retired (use scripts/translate_catalog_v2.py); set AOEP_LEGACY_TRANSLATE=1 to run it anyway"
  exit 0
fi

ROOT="${AOEP_TRANSLATE_ROOT:-${HOME}/code/gs-wt/spark-eval-gates}"
PY="${AOEP_VENV:-${HOME}/code/getschoolled/.venv}/bin/python"
cd "${ROOT}" || exit 1
export SPEECH_BASE_URL="http://127.0.0.1:8002"
export AOEP_COURSE_TRANSLATION_DIR="${AOEP_COURSE_TRANSLATION_DIR:-${HOME}/.cache/aoep/course_translations}"
export TRANSLATION_TIMEOUT_S="${TRANSLATION_TIMEOUT_S:-180}"
export RATE_LIMIT_DISABLED=1
export NLLB_DEVICE=cpu
export AOEP_ALLOW_CPU=1   # explicit: the CUDA-always policy ignores NLLB_DEVICE=cpu unless this is set
export NLLB_MODEL="${NLLB_MODEL:-facebook/nllb-200-distilled-600M}"
export PYTHONPATH="${ROOT}/packages/shared/src${PYTHONPATH:+:${PYTHONPATH}}"

nllb_pid=""
cleanup() { [ -n "${nllb_pid}" ] && kill -0 "${nllb_pid}" 2>/dev/null && kill "${nllb_pid}" 2>/dev/null; return 0; }
trap 'cleanup' EXIT

start_nllb() {
  if curl -sf -m 3 "${SPEECH_BASE_URL}/languages" >/dev/null 2>&1; then su_log "nllb already up"; return 0; fi
  su_log "starting nllb on cpu"
  "${PY}" -m uvicorn speech_gw.main:app --app-dir "${ROOT}/services/speech/src" --host 127.0.0.1 --port 8002 &
  nllb_pid=$!
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 15 20 25 30; do
    curl -sf -m 3 "${SPEECH_BASE_URL}/languages" >/dev/null 2>&1 && { su_log "nllb up pid=${nllb_pid}"; return 0; }
    sleep 1
  done
  su_log "nllb did not answer"
  return 1
}

while [ "${SU_STOP}" = 0 ]; do
  su_wait_memory "${AOEP_TRANSLATE_MIN_FREE_MB:-12288}" "translate"
  [ "${SU_STOP}" = 1 ] && break
  if ! start_nllb; then su_sleep 60; continue; fi
  su_log "translate batch start"
  su_run_child "${PY}" scripts/translate_courses_batch.py --audio-only --concurrency 1 --verbose \
    --language es --language fr --language de --language it --language pt \
    --language nl --language pl --language ru --language uk --language tr \
    --language ar --language he --language hi --language bn --language ur \
    --language fa --language zh --language ja --language ko --language vi \
    --language yue
  su_log "translate batch exit=$?"
  su_once_done && break
  su_sleep 60
done
exit 0
