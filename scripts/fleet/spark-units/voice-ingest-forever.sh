#!/usr/bin/env bash
# Resume the CosyVoice voice-data ingest after a reboot without the three-worker pile-up.
# One worker while STEM training is alive; never starts the Khmer fine-tune.
#
# What changed from the version that ran before (behaviour otherwise identical):
#   - runs from a configurable root (AOEP_INGEST_ROOT, default: the repo this script lives in) with the shared venv
#     (AOEP_VENV, default ~/code/getschoolled/.venv) so it picks up new code without switching a checkout;
#   - AOEP_ASR_DEVICE=cuda is exported ONLY when the CUDA policy passes (aoep_shared.devices.cuda_smoke). If it fails
#     the ingest does NOT start on the CPU silently: it logs the reason and retries in 5 minutes;
#   - worker count is capped by AOEP_INGEST_MAX_WORKERS (default 1) on top of the reboot policy, so the GPU is not
#     oversubscribed. The ASR bursts take ~/.gs-gpu.lock themselves (aoep_shared.gpu_lock: short wait, then proceed).
set -u
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ROOT="${AOEP_INGEST_ROOT:-${SU_ROOT}}"
VENV="${AOEP_VENV:-${HOME}/code/getschoolled/.venv}"
PY="${VENV}/bin/python"
[ -x "${PY}" ] || PY="$(command -v python3)"
MAX_WORKERS="${AOEP_INGEST_MAX_WORKERS:-1}"

cd "${ROOT}" || { su_log "ingest root ${ROOT} not found"; exit 1; }
export PATH="${VENV}/bin:${PATH}"
export PYTHONPATH="${ROOT}/packages/shared/src${PYTHONPATH:+:${PYTHONPATH}}"
export AOEP_HOST_ROLE="${AOEP_HOST_ROLE:-spark}"
export AOEP_ASR_ENGINE="${AOEP_ASR_ENGINE:-openai-whisper}"
export AOEP_ASR_MODEL="${AOEP_ASR_MODEL:-large-v3}"
export AOEP_ASR_KM_ENGINE="${AOEP_ASR_KM_ENGINE:-mms}"
export AOEP_ASR_DETECT_LANGUAGE="${AOEP_ASR_DETECT_LANGUAGE:-1}"
export YT_DLP_COOKIES_FROM_BROWSER="${YT_DLP_COOKIES_FROM_BROWSER:-chromium:${HOME}/snap/chromium/common/chromium}"
export YT_DLP_PLAYER_CLIENT="${YT_DLP_PLAYER_CLIENT:-web_safari}"
export YT_DLP_SLEEP_REQUESTS="${YT_DLP_SLEEP_REQUESTS:-2}"

# 0 when the CUDA policy passes (prints nothing), 1 otherwise (prints the reason).
cuda_policy_ok() {
  "${PY}" - <<'PYEOF'
import sys
try:
    from aoep_shared import devices
    ok, msg = devices.cuda_smoke()
except Exception as exc:  # noqa: BLE001
    ok, msg = False, f"{type(exc).__name__}: {exc}"
if not ok:
    print(msg)
sys.exit(0 if ok else 1)
PYEOF
}

worker_count() {
  local free_mb training=0 n=1
  free_mb="$(su_free_mb)"
  if pgrep -f 'training/spark_nightly.sh|run_finetune.py' >/dev/null 2>&1; then training=1; fi
  if [ -f "${ROOT}/training/reboot_policy.py" ]; then
    n="$(FREE_MB="${free_mb:-0}" TRAINING="${training}" PYTHONPATH="${ROOT}/training" "${PY}" -c \
      'from reboot_policy import ingest_workers; import os; print(ingest_workers(int(os.environ["FREE_MB"]), os.environ["TRAINING"]=="1"))' 2>/dev/null || echo 1)"
  fi
  case "${n}" in ''|*[!0-9]*) n=1 ;; esac
  [ "${n}" -gt "${MAX_WORKERS}" ] && n="${MAX_WORKERS}"
  [ "${n}" -lt 1 ] && n=1
  echo "${n}"
}

su_log "voice ingest loop start root=${ROOT} max_workers=${MAX_WORKERS}"
while [ "${SU_STOP}" = 0 ]; do
  if pgrep -f 'scripts/cosyvoice_batch_ingest.py' >/dev/null 2>&1; then
    su_once_done && break
    su_sleep 120
    continue
  fi
  su_wait_memory 16384 "ingest"
  [ "${SU_STOP}" = 1 ] && break

  why="$(cuda_policy_ok)"
  if [ $? -ne 0 ]; then
    su_log "CUDA policy failed (${why}); not starting the ingest on the CPU. retrying in 300s"
    su_once_done && break
    su_sleep 300
    continue
  fi
  export AOEP_ASR_DEVICE=cuda

  workers="$(worker_count)"
  su_log "voice ingest restart workers=${workers}"
  su_run_child "${PY}" scripts/cosyvoice_batch_ingest.py --pool km,zh,yue,zh_tw --workers "${workers}"
  su_log "priority pools exit=$?"
  [ "${SU_STOP}" = 1 ] && break
  workers="$(worker_count)"
  su_run_child "${PY}" scripts/cosyvoice_batch_ingest.py \
    --pool en,en_gb,en_au,tl,vi,th,es,fr,de,ru,it,pt,nl,pl,uk,tr,ar,he,hi,bn,ur,fa,ja,ko,id,sw,el,cs --workers "${workers}"
  su_log "remaining pools exit=$?"
  [ "${SU_STOP}" = 1 ] && break
  su_once_done && break
  su_sleep 120
done
su_log "voice ingest loop stopped"
exit 0
