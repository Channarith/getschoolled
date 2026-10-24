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
ROOT="$PWD"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

SESSIONS="${SESSIONS:-training/data/sample_sessions.json}"
OUTPUT_DIR="${OUTPUT_DIR:-training/out/adapter}"
DEVICE="${DEVICE:-auto}"
TRAIN_JSONL="training/data/train.jsonl"
EVAL_JSONL="training/data/eval.jsonl"

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

echo "==> 1/3 export sessions -> JSONL"
"$PY" training/export.py --in "$SESSIONS" --out "$TRAIN_JSONL" \
  --eval-out "$EVAL_JSONL" --eval-split 0.2 || \
  "$PY" training/export.py --in "$SESSIONS" --out "$TRAIN_JSONL"

if [ "${CHECK_ONLY:-0}" = "1" ]; then
  echo "==> validate only (CHECK_ONLY=1)"
  "$PY" training/run_finetune.py --check --config training/config/finetune.yaml \
    --train "$TRAIN_JSONL"
  # Also prove the tutor-data path end to end without a GPU: seed, tutor sessions, quality gate, export.
  CHECK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gs-check.XXXXXX")"
  trap 'rm -rf "$CHECK_DIR"' EXIT
  "$PY" training/spark_seed_sessions.py --curriculum sample-curriculum \
    --sample training/data/sample_sessions.json --out "$CHECK_DIR/seed.json"
  "$PY" training/tutor_sessions.py --curriculum sample-curriculum --out "$CHECK_DIR/tutor.json"
  "$PY" training/quality_gate.py --in "$CHECK_DIR/seed.json" "$CHECK_DIR/tutor.json" \
    --out "$CHECK_DIR/clean.json" --report "$CHECK_DIR/quality.json"
  "$PY" training/export.py --in "$CHECK_DIR/clean.json" --out "$CHECK_DIR/train.jsonl" \
    --eval-out "$CHECK_DIR/eval.jsonl" --eval-split 0.1
  "$PY" training/run_finetune.py --check --config training/config/finetune.spark.yaml \
    --train "$CHECK_DIR/train.jsonl"
  echo "==> CHECK_ONLY ok"
  exit 0
fi

if [ -z "${BASE_MODEL:-}" ]; then
  echo "ERROR: set BASE_MODEL=/path/to/local/base-model for a real run." >&2
  echo "       (or run with CHECK_ONLY=1 to validate the pipeline)" >&2
  exit 1
fi

# Long stages run under the resource limits (RAM ceiling, CPU quota, timeout, no orphans).
. "$ROOT/training/lib_limits.sh"
gs_preflight "${NEED_GB:-12}" || exit $?

echo "==> 2/3 fine-tune (offline, device=$DEVICE)"
gs_stage "train" "${TRAIN_TIMEOUT_MIN:-300}" "$PY" training/run_finetune.py --offline --device "$DEVICE" \
  --base-model "$BASE_MODEL" --config training/config/finetune.yaml \
  --train "$TRAIN_JSONL" --output "$OUTPUT_DIR"

if [ -f "$EVAL_JSONL" ]; then
  echo "==> 3/3 evaluate"
  gs_stage "eval" "${EVAL_TIMEOUT_MIN:-120}" "$PY" training/evaluate.py --offline --device "$DEVICE" \
    --base-model "$BASE_MODEL" --adapter "$OUTPUT_DIR" --eval "$EVAL_JSONL"
fi
echo "==> done. adapter at $OUTPUT_DIR"
