#!/usr/bin/env bash
# One-epoch CosyVoice-300M LLM fine-tune on the deduped Khmer export.
# GPU work takes ~/.gs-gpu.lock. Checkpoints stay under output/spark/cosyvoice.
# This script does not copy weights into pretrained_models and does not
# restart or retarget the live CosyVoice server.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCAN_ROOT="${SCAN_ROOT:-/home/nvidia/code/getschoolled/output}"
DEST="${DEST:-$ROOT/output/spark/cosyvoice}"
COSY="${COSYVOICE_REPO:-$HOME/code/CosyVoice}"
PY_AOEP="${AOEP_PYTHON:-/home/nvidia/code/getschoolled/.venv/bin/python}"
PY_CV="${COSYVOICE_PYTHON:-$COSY/.venv/bin/python}"
LOCK="${GS_GPU_LOCK:-$HOME/.gs-gpu.lock}"
MODEL_SRC="$COSY/pretrained_models/CosyVoice-300M"
VOICES_ROOT="${VOICES_ROOT:-$ROOT/voices}"

export PYTHONPATH="$ROOT/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$DEST"
"$PY_AOEP" "$ROOT/scripts/spark_cosyvoice_manifest.py" \
  --scan-root "$SCAN_ROOT" \
  --dest "$DEST" \
  --cosyvoice-repo "$COSY" \
  --voices-root "$VOICES_ROOT"

KM_SRC="$DEST/km_exported/04_cosyvoice/train"
TRAIN_DIR="$DEST/km/train"
DEV_DIR="$DEST/km/dev"
EXP_DIR="$DEST/km/exp/llm"
LOG_DIR="$DEST/km/logs"
CONF="$DEST/km/cosyvoice_sft.yaml"
mkdir -p "$TRAIN_DIR" "$DEV_DIR" "$EXP_DIR" "$LOG_DIR"

"$PY_AOEP" - << PY
import json
from pathlib import Path
from aoep_shared.cosyvoice_ingest.spark_manifest import (
    patch_sft_yaml,
    split_kaldi_holdout,
    training_decision,
)

census = json.loads(Path("$DEST/census.json").read_text(encoding="utf-8"))
km = census["km_exported"]
decision = training_decision("km", km["utterances"], km["seconds"])
salane = census["decision"]["salane"]
split = split_kaldi_holdout(Path("$KM_SRC"), Path("$TRAIN_DIR"), Path("$DEV_DIR"), holdout=4, seed=17)
stock = Path("$COSY/examples/libritts/cosyvoice/conf/cosyvoice.yaml").read_text(encoding="utf-8")
Path("$CONF").write_text(patch_sft_yaml(stock, language="km", max_epoch=1), encoding="utf-8")
out = {
    "decision": decision,
    "salane": salane,
    "split": split,
    "promoted": False,
    "model_dir": "$EXP_DIR",
}
Path("$DEST/km/prepare.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
if not decision["run"]:
    raise SystemExit(2)
PY

echo "Salane decision is in $DEST/km/prepare.json (no second run when run=false)."
if [[ -f "$TRAIN_DIR/utt2speech_token.pt" && -f "$DEV_DIR/utt2speech_token.pt" && -f "$TRAIN_DIR/utt2embedding.pt" && -f "$DEV_DIR/utt2embedding.pt" ]]; then
  echo "Reusing existing CPU embeddings and speech tokens."
else
  echo "Extracting campplus embeddings and speech tokens on CPU (no GPU lock)."
  "$PY_CV" "$ROOT/scripts/spark_extract_embedding.py" \
    --dir "$TRAIN_DIR" \
    --onnx_path "$MODEL_SRC/campplus.onnx" \
    --num_thread 4
  "$PY_CV" "$ROOT/scripts/spark_extract_embedding.py" \
    --dir "$DEV_DIR" \
    --onnx_path "$MODEL_SRC/campplus.onnx" \
    --num_thread 4
  "$PY_CV" "$ROOT/scripts/spark_extract_speech_token.py" \
    --dir "$TRAIN_DIR" \
    --onnx_path "$MODEL_SRC/speech_tokenizer_v1.onnx" \
    --num_thread 2
  "$PY_CV" "$ROOT/scripts/spark_extract_speech_token.py" \
    --dir "$DEV_DIR" \
    --onnx_path "$MODEL_SRC/speech_tokenizer_v1.onnx" \
    --num_thread 2
fi

"$PY_CV" "$ROOT/scripts/spark_make_parquet.py" \
  --src_dir "$TRAIN_DIR" --des_dir "$TRAIN_DIR/parquet"
"$PY_CV" "$ROOT/scripts/spark_make_parquet.py" \
  --src_dir "$DEV_DIR" --des_dir "$DEV_DIR/parquet"

PYDEPS="$DEST/km/pydeps"
if ! PYTHONPATH="$PYDEPS${PYTHONPATH:+:$PYTHONPATH}" "$PY_CV" -c 'import tensorboard' >/dev/null 2>&1; then
  echo "Installing tensorboard into $PYDEPS (not the live CosyVoice venv)."
  "$COSY/.venv/bin/pip" install --target "$PYDEPS" 'tensorboard==2.20.0'
  rm -rf "$PYDEPS"/numpy* "$PYDEPS"/numpy "$PYDEPS"/bin
fi

STUB="$DEST/km/deepspeed_stub"
mkdir -p "$STUB/deepspeed/runtime/zero"
cat > "$STUB/deepspeed/__init__.py" << 'EOF'
def add_config_arguments(parser):
    return parser


def initialize(*args, **kwargs):
    raise RuntimeError("this Spark run uses torch_ddp, not deepspeed")


def init_distributed(*args, **kwargs):
    raise RuntimeError("this Spark run uses torch_ddp, not deepspeed")
EOF
printf '' > "$STUB/deepspeed/runtime/__init__.py"
printf '' > "$STUB/deepspeed/runtime/zero/__init__.py"
cat > "$STUB/deepspeed/runtime/zero/stage_1_and_2.py" << 'EOF'
def estimate_zero2_model_states_mem_needs_all_live(*args, **kwargs):
    return None
EOF

LOG="$LOG_DIR/train-$(date -u +%Y%m%dT%H%M%SZ).log"
echo "GPU train under flock $LOCK -> $LOG"
START=$(date +%s)
set +e
flock "$LOCK" env \
  PYTHONPATH="$STUB:$PYDEPS:$COSY:$COSY/third_party/Matcha-TTS" \
  CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
  COSYVOICE_TRAIN_PY="$COSY/cosyvoice/bin/train.py" \
  "$COSY/.venv/bin/torchrun" \
  --nnodes=1 --nproc_per_node=1 \
  --rdzv_id=1986 --rdzv_backend=c10d --rdzv_endpoint=localhost:29561 \
  "$ROOT/scripts/spark_train_entry.py" \
  --train_engine torch_ddp \
  --config "$CONF" \
  --train_data "$TRAIN_DIR/parquet/data.list" \
  --cv_data "$DEV_DIR/parquet/data.list" \
  --onnx_path "$MODEL_SRC/campplus.onnx" \
  --model llm \
  --checkpoint "$MODEL_SRC/llm.pt" \
  --model_dir "$EXP_DIR" \
  --tensorboard_dir "$DEST/km/tensorboard" \
  --num_workers 0 --prefetch 10 \
  > "$LOG" 2>&1
TRAIN_RC=$?
set -e
END=$(date +%s)
ELAPSED=$((END - START))

"$PY_AOEP" - << PY
import json
from pathlib import Path
from aoep_shared.cosyvoice_ingest.spark_manifest import parse_cv_metrics

log_path = Path("$LOG")
text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
rows = parse_cv_metrics(text)
prepare = json.loads(Path("$DEST/km/prepare.json").read_text(encoding="utf-8"))
metrics = {
    "promoted": False,
    "train_exit_code": $TRAIN_RC,
    "elapsed_seconds": $ELAPSED,
    "log": str(log_path),
    "model_dir": "$EXP_DIR",
    "checkpoint_read_only": "$MODEL_SRC/llm.pt",
    "cv": rows,
    "prepare": prepare,
    "note": "Candidate only. Not copied into pretrained_models or the live server.",
}
Path("$DEST/km/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"exit": $TRAIN_RC, "elapsed_seconds": $ELAPSED, "cv_rows": len(rows)}, indent=2))
PY

echo "elapsed_seconds=$ELAPSED exit=$TRAIN_RC log=$LOG"
echo "not promoted"
exit "$TRAIN_RC"
