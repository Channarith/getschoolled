#!/usr/bin/env bash
# One-command OFFLINE training run for the education LLM (Linux/Ubuntu).
#
# Usage:
#   BASE_MODEL=/models/education-base ./training/train.sh
#
# Env vars:
#   BASE_MODEL   local path to the base model dir (required for a real run)
#   SESSIONS     sessions JSON to export (default: training/data/sample_sessions.json)
#   OUTPUT_DIR   where the LoRA adapter is written (default: training/out/adapter)
#   DEVICE       auto | cpu | cuda (default: auto)
#   CHECK_ONLY   set to 1 to validate config+data and skip training
#
# Fully offline: sets HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE so nothing hits the
# network; point BASE_MODEL at a locally-downloaded model.
set -euo pipefail

cd "$(dirname "$0")/.."   # repo root

SESSIONS="${SESSIONS:-training/data/sample_sessions.json}"
OUTPUT_DIR="${OUTPUT_DIR:-training/out/adapter}"
DEVICE="${DEVICE:-auto}"
TRAIN_JSONL="training/data/train.jsonl"
EVAL_JSONL="training/data/eval.jsonl"

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

echo "==> 1/3 export sessions -> JSONL"
python3 training/export.py --in "$SESSIONS" --out "$TRAIN_JSONL" \
  --eval-out "$EVAL_JSONL" --eval-split 0.2 || \
  python3 training/export.py --in "$SESSIONS" --out "$TRAIN_JSONL"

if [ "${CHECK_ONLY:-0}" = "1" ]; then
  echo "==> validate only (CHECK_ONLY=1)"
  python3 training/run_finetune.py --check --config training/config/finetune.yaml \
    --train "$TRAIN_JSONL"
  exit 0
fi

if [ -z "${BASE_MODEL:-}" ]; then
  echo "ERROR: set BASE_MODEL=/path/to/local/base-model for a real run." >&2
  echo "       (or run with CHECK_ONLY=1 to validate the pipeline)" >&2
  exit 1
fi

echo "==> 2/3 fine-tune (offline, device=$DEVICE)"
python3 training/run_finetune.py --offline --device "$DEVICE" \
  --base-model "$BASE_MODEL" --config training/config/finetune.yaml \
  --train "$TRAIN_JSONL" --output "$OUTPUT_DIR"

if [ -f "$EVAL_JSONL" ]; then
  echo "==> 3/3 evaluate"
  python3 training/evaluate.py --offline --device "$DEVICE" \
    --base-model "$BASE_MODEL" --adapter "$OUTPUT_DIR" --eval "$EVAL_JSONL"
fi
echo "==> done. adapter at $OUTPUT_DIR"
