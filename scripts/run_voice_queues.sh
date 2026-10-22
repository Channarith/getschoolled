#!/usr/bin/env bash
# Voice corpus training queues: Khmer + Chinese pools first, then the rest.
# Captions first, MMS for Khmer-native speech, Whisper large-v3 otherwise.
# Safe to re-run: downloaded audio is cached and each channel re-exports.
set -u
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
export AOEP_ASR_ENGINE="${AOEP_ASR_ENGINE:-openai-whisper}"
export AOEP_ASR_MODEL="${AOEP_ASR_MODEL:-large-v3}"
export AOEP_ASR_KM_ENGINE="${AOEP_ASR_KM_ENGINE:-mms}"
export AOEP_ASR_DETECT_LANGUAGE="${AOEP_ASR_DETECT_LANGUAGE:-1}"
export YT_DLP_COOKIES_FROM_BROWSER="${YT_DLP_COOKIES_FROM_BROWSER:-chromium:/home/nvidia/snap/chromium/common/chromium}"
export YT_DLP_PLAYER_CLIENT="${YT_DLP_PLAYER_CLIENT:-web_safari}"
export YT_DLP_SLEEP_REQUESTS="${YT_DLP_SLEEP_REQUESTS:-2}"
# Back off when YouTube says the page must be reloaded, and refuse a second
# ASR model when free RAM is already under these floors. The queue also
# shrinks --workers to what MemAvailable can hold.
export YT_DLP_LIMIT_BACKOFF="${YT_DLP_LIMIT_BACKOFF:-30}"
export YT_DLP_LIMIT_STREAK="${YT_DLP_LIMIT_STREAK:-3}"
export YT_DLP_COOLDOWN_SEC="${YT_DLP_COOLDOWN_SEC:-120}"
export AOEP_INGEST_MIN_FREE_MB="${AOEP_INGEST_MIN_FREE_MB:-8192}"
export AOEP_INGEST_WORKER_MB="${AOEP_INGEST_WORKER_MB:-6144}"
export AOEP_ASR_MIN_FREE_MB="${AOEP_ASR_MIN_FREE_MB:-4096}"
export AOEP_ASR_SINGLE_MODEL_MB="${AOEP_ASR_SINGLE_MODEL_MB:-12288}"
echo "=== priority pools km,zh,yue,zh_tw start $(date) ==="
.venv/bin/python scripts/cosyvoice_batch_ingest.py --pool km,zh,yue,zh_tw --workers 3
echo "=== remaining pools start $(date) ==="
.venv/bin/python scripts/cosyvoice_batch_ingest.py --pool en,en_gb,en_au,tl,vi,th,es,fr,de,ru,it,pt,nl,pl,uk,tr,ar,he,hi,bn,ur,fa,ja,ko,id,sw,el,cs --workers 3
echo "=== all voice queues done $(date) ==="
