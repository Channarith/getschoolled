#!/usr/bin/env bash
# Keep the Spark STEM QLoRA cycle running: one cycle at a time (spark_nightly.sh holds ~/.gs-gpu.lock itself).
#
# Pause switch: while ~/.gs-hold/stem-train (or $GS_STEM_HOLD_FILE) exists NO new cycle starts; a cycle already
# running finishes. The file's text is logged once. Delete it to resume. (Freezing this script with SIGSTOP also
# pauses it, but a hold file survives reboots and is visible to everyone.)
#
# Environment (all optional):
#   AOEP_TRAIN_WORKTREE  worktree that holds training/ (default: the repo this script lives in)
#   BASE_MODEL, PYTHON   as before; defaults are the paths the original service used
#   AOEP_TRAIN_MIN_FREE_MB  wait for this much MemAvailable before a cycle (default 12288)
#   GS_STEM_HOLD_FILE    pause file (default ~/.gs-hold/stem-train)
set -u
# shellcheck source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

WORKTREE="${AOEP_TRAIN_WORKTREE:-${SU_ROOT}}"
HOLD="${GS_STEM_HOLD_FILE:-${HOME}/.gs-hold/stem-train}"
STEM_WT="${HOME}/code/gs-wt/spark-train-stem"

export BASE_MODEL="${BASE_MODEL:-${STEM_WT}/models/weights/qwen2.5-7b-instruct}"
if [ -z "${PYTHON:-}" ]; then
  for cand in "${STEM_WT}/.venv/bin/python" "${HOME}/code/getschoolled/.venv/bin/python" "$(command -v python3 || true)"; do
    if [ -n "${cand}" ] && [ -x "${cand}" ]; then PYTHON="${cand}"; break; fi
  done
fi
export PYTHON

cd "${WORKTREE}" || { su_log "worktree ${WORKTREE} not found"; exit 1; }
mkdir -p output/spark/logs
su_log "llm loop start worktree=${WORKTREE} hold=${HOLD}"

announced=0
while [ "${SU_STOP}" = 0 ]; do
  if [ -e "${HOLD}" ]; then
    if [ "${announced}" = 0 ]; then
      su_log "STEM training held by ${HOLD}: $(head -c 200 "${HOLD}" 2>/dev/null | tr '\n' ' ')"
      announced=1
    fi
    su_once_done && break
    su_sleep 60
    continue
  fi
  if [ "${announced}" = 1 ]; then
    su_log "hold file removed: resuming"
    announced=0
  fi

  su_wait_memory "${AOEP_TRAIN_MIN_FREE_MB:-12288}" "llm"
  [ "${SU_STOP}" = 1 ] && break
  su_log "llm cycle start"
  su_run_child ./training/spark_nightly.sh
  rc=$?
  su_log "llm cycle exit=${rc}"
  [ "${SU_STOP}" = 1 ] && break
  su_once_done && break
  if [ "${rc}" -ne 0 ]; then su_sleep 120; else su_sleep 30; fi
done
su_log "llm loop stopped"
exit 0
