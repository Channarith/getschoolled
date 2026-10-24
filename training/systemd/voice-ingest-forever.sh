#!/usr/bin/env bash
# Resume voice ingest after a reboot without the three-worker pile-up.
# One worker while STEM training is alive. Never starts Khmer fine-tune.
set -u
ROOT="/home/nvidia/code/getschoolled"
GATES="/home/nvidia/code/gs-wt/spark-eval-gates"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
export AOEP_ASR_ENGINE="${AOEP_ASR_ENGINE:-openai-whisper}"
export AOEP_ASR_MODEL="${AOEP_ASR_MODEL:-large-v3}"
export AOEP_ASR_KM_ENGINE="${AOEP_ASR_KM_ENGINE:-mms}"
export AOEP_ASR_DETECT_LANGUAGE="${AOEP_ASR_DETECT_LANGUAGE:-1}"
export YT_DLP_COOKIES_FROM_BROWSER="${YT_DLP_COOKIES_FROM_BROWSER:-chromium:/home/nvidia/snap/chromium/common/chromium}"
export YT_DLP_PLAYER_CLIENT="${YT_DLP_PLAYER_CLIENT:-web_safari}"
export YT_DLP_SLEEP_REQUESTS="${YT_DLP_SLEEP_REQUESTS:-2}"

worker_count() {
  local free_mb training=0
  free_mb="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
  if pgrep -f 'training/spark_nightly.sh|run_finetune.py' >/dev/null 2>&1; then
    training=1
  fi
  if [[ -f "$GATES/training/reboot_policy.py" ]]; then
    FREE_MB="$free_mb" TRAINING="$training" PYTHONPATH="$GATES/training" \
      python3 -c 'from reboot_policy import ingest_workers; import os; print(ingest_workers(int(os.environ["FREE_MB"]), os.environ["TRAINING"]=="1"))' \
      && return 0
  fi
  echo 1
}

wait_for_memory() {
  local need_mb=16384 free_mb _
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 30; do
    free_mb="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
    if [[ -z "$free_mb" || "$free_mb" -ge "$need_mb" ]]; then
      echo "=== ingest memory ok free_mb=${free_mb} $(date -Is) ==="
      return 0
    fi
    echo "=== ingest waiting free_mb=${free_mb} need_mb=${need_mb} $(date -Is) ==="
    sleep 20
  done
}

while true; do
  if pgrep -f 'scripts/cosyvoice_batch_ingest.py' >/dev/null 2>&1; then
    sleep 120
    continue
  fi
  wait_for_memory
  workers="$(worker_count)"
  echo "=== voice ingest restart workers=${workers} $(date -Is) ==="
  python3 scripts/cosyvoice_batch_ingest.py --pool km,zh,yue,zh_tw --workers "$workers"
  echo "=== priority pools exit=$? $(date -Is) ==="
  workers="$(worker_count)"
  python3 scripts/cosyvoice_batch_ingest.py --pool en,en_gb,en_au,tl,vi,th,es,fr,de,ru,it,pt,nl,pl,uk,tr,ar,he,hi,bn,ur,fa,ja,ko,id,sw,el,cs --workers "$workers"
  echo "=== remaining pools exit=$? $(date -Is) ==="
  sleep 120
done
