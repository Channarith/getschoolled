#!/usr/bin/env bash
# Keep the Khmer CosyVoice fine-tune running. GPU sections take ~/.gs-gpu.lock (inside the cycle script).
# Held by default behaviour: while ~/.local/share/aoep-train/hold-voice-train exists it never loads base weights.
# The script does not copy weights into the live CosyVoice server.
#
# Environment: AOEP_VOICE_WORKTREE (default ~/code/gs-wt/spark-cosyvoice-khmer), AOEP_TRAIN_MIN_FREE_MB,
#              PYTORCH_CUDA_ALLOC_CONF, AOEP_VOICE_HOLD_FILE.
set -u
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

HOLD="${AOEP_VOICE_HOLD_FILE:-${HOME}/.local/share/aoep-train/hold-voice-train}"
WORKTREE="${AOEP_VOICE_WORKTREE:-${HOME}/code/gs-wt/spark-cosyvoice-khmer}"

if [ -f "${HOLD}" ]; then
  su_log "voice train held; not loading base weights"
  su_once_done && exit 0
  su_sleep 3600
  exit 0
fi

cd "${WORKTREE}" || { su_log "worktree ${WORKTREE} not found"; exit 1; }
mkdir -p output/spark/cosyvoice-khmer/multi
# Set before torch starts. expandable_segments avoids the fragmented CUDA context that failed with NV_ERR_NO_MEMORY.
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
LOG_DIR="output/spark/cosyvoice-khmer/multi/km/logs"

while [ "${SU_STOP}" = 0 ]; do
  latest=""
  if compgen -G "${LOG_DIR}"/train-*.log >/dev/null; then
    latest="$(ls -1t "${LOG_DIR}"/train-*.log | head -1)"
  fi
  if [ -n "${latest}" ] && grep -q -E 'SIGKILL|out of memory|exitcode: -9|exitcode  : -9' "${latest}"; then
    su_log "previous train died on memory; sleeping 600s"
    su_sleep 600
    [ "${SU_STOP}" = 1 ] && break
  fi
  su_wait_memory "${AOEP_TRAIN_MIN_FREE_MB:-12288}" "voice"
  [ "${SU_STOP}" = 1 ] && break
  su_log "voice cycle start"
  su_run_child ./scripts/spark_cosyvoice_khmer_multiepoch.sh
  rc=$?
  su_log "voice cycle exit=${rc}"
  [ "${SU_STOP}" = 1 ] && break
  su_once_done && break
  if [ "${rc}" -eq 137 ] || [ "${rc}" -lt 0 ]; then
    su_log "train was killed (exit ${rc}); sleeping 600s"
    su_sleep 600
  elif [ "${rc}" -ne 0 ]; then
    su_sleep 180
  else
    su_sleep 30
  fi
done
su_log "voice loop stopped"
exit 0
