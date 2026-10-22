#!/usr/bin/env bash
# One-epoch CosyVoice-300M LLM fine-tune on the 461-minute Khmer pool.
# GPU work takes ~/.gs-gpu.lock. Checkpoints stay under output/spark/cosyvoice-khmer.
# This script does not copy weights into pretrained_models, does not edit the
# serving config, and does not restart the live CosyVoice server. Salane is skipped.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
POOL="${POOL_DIR:-/home/nvidia/code/gs-wt/spark-voice-data/output/spark/voice-data/km/04_cosyvoice/train}"
DEST="${DEST:-$ROOT/output/spark/cosyvoice-khmer}"
COSY="${COSYVOICE_REPO:-$HOME/code/CosyVoice}"
PY_AOEP="${AOEP_PYTHON:-/home/nvidia/code/getschoolled/.venv/bin/python}"
PY_CV="${COSYVOICE_PYTHON:-$COSY/.venv/bin/python}"
LOCK="${GS_GPU_LOCK:-$HOME/.gs-gpu.lock}"
MODEL_SRC="$COSY/pretrained_models/CosyVoice-300M"
BASELINE_CKPT="${BASELINE_CKPT:-/home/nvidia/code/gs-wt/spark-cosyvoice-ft/output/spark/cosyvoice/km/exp/llm/epoch_0_whole.pt}"
RDZV_PORT="${RDZV_PORT:-29573}"

export PYTHONPATH="$ROOT/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}"
# Set before any CUDA alloc. expandable_segments avoids the fragmented-context
# NV_ERR_NO_MEMORY failures seen when train and eval start back to back.
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

if [[ ! -f "$POOL/wav.scp" || ! -f "$POOL/text" ]]; then
  echo "Khmer pool missing at $POOL" >&2
  exit 2
fi
if [[ ! -f "$MODEL_SRC/llm.pt" ]]; then
  echo "CosyVoice-300M weights missing at $MODEL_SRC" >&2
  exit 2
fi

TRAIN_DIR="$DEST/km/train"
DEV_DIR="$DEST/km/dev"
EXP_DIR="$DEST/km/exp/llm"
LOG_DIR="$DEST/km/logs"
CONF="$DEST/km/cosyvoice_sft.yaml"
mkdir -p "$TRAIN_DIR" "$DEV_DIR" "$EXP_DIR" "$LOG_DIR"

echo "Salane skipped: that pool has no consented audio."
"$PY_AOEP" - << PY
import json
import shutil
from pathlib import Path
from aoep_shared.cosyvoice_ingest.spark_manifest import patch_sft_yaml, split_kaldi_holdout

pool = Path("$POOL")
snap = Path("$DEST/pool")
snap.mkdir(parents=True, exist_ok=True)
for name in ("wav.scp", "text", "utt2spk", "utt2lang"):
    src = pool / name
    if src.is_file():
        shutil.copyfile(src, snap / name)
split = split_kaldi_holdout(snap, Path("$TRAIN_DIR"), Path("$DEV_DIR"), holdout=64, seed=17)
stock = Path("$COSY/examples/libritts/cosyvoice/conf/cosyvoice.yaml").read_text(encoding="utf-8")
Path("$CONF").write_text(
    patch_sft_yaml(stock, language="km", max_epoch=1, token_max_length=700),
    encoding="utf-8",
)
out = {
    "pool": str(pool),
    "salane": "skipped",
    "split": split,
    "token_max_length": 700,
    "promoted": False,
    "serving_config": "unchanged",
    "model_dir": "$EXP_DIR",
}
Path("$DEST/km/prepare.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
if split["train_utterances"] < 1:
    raise SystemExit(2)
PY

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
export LOG_DIR
echo "Checking free memory before taking the GPU lock."
"$PY_AOEP" - << 'PY'
import os
import time
from pathlib import Path

from aoep_shared.cosyvoice_ingest.guard import available_mb, consume_oom_backoff

delay = consume_oom_backoff(Path(os.environ["LOG_DIR"]))
if delay:
    print(f"previous run died on memory; sleeping {int(delay)}s before the GPU", flush=True)
    time.sleep(delay)
floor = int(os.environ.get("AOEP_TRAIN_MIN_FREE_MB", "12288") or "12288")
attempts = int(os.environ.get("AOEP_MEMORY_WAIT_ATTEMPTS", "30") or "30")
step = int(os.environ.get("AOEP_MEMORY_WAIT_SEC", "20") or "20")
free = None
for index in range(max(1, attempts)):
    free = available_mb()
    if free is None or floor <= 0 or free >= floor:
        print(f"memory ok free_mb={free}", flush=True)
        break
    print(f"waiting for memory free_mb={free} need_mb={floor}", flush=True)
    if index + 1 < attempts and step > 0:
        time.sleep(step)
else:
    print(f"memory still tight free_mb={free}; one training job will start", flush=True)
PY

echo "GPU train+eval under flock $LOCK -> $LOG"
# One lock covers train and eval so the other GPU job cannot start in the gap
# and leave no context memory for the checkpoint comparison.
exec 9>"$LOCK"
flock 9
START=$(date +%s)
set +e
env \
  PYTHONPATH="$STUB:$PYDEPS:$ROOT/packages/shared/src:$COSY:$COSY/third_party/Matcha-TTS" \
  PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF}" \
  CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
  COSYVOICE_TRAIN_PY="$COSY/cosyvoice/bin/train.py" \
  "$COSY/.venv/bin/torchrun" \
  --nnodes=1 --nproc_per_node=1 \
  --rdzv_id=1988 --rdzv_backend=c10d --rdzv_endpoint="localhost:${RDZV_PORT}" \
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
    "serving_config": "unchanged",
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
if [[ "$TRAIN_RC" -ne 0 ]]; then
  echo "train failed; eval skipped; not promoted"
  if [[ "$TRAIN_RC" -eq 137 || "$TRAIN_RC" -lt 0 ]]; then
    echo "train process was killed (exit $TRAIN_RC); next start will back off" >> "$LOG_DIR/last_failure.txt"
  fi
  exit "$TRAIN_RC"
fi

CANDIDATE_CKPT="$EXP_DIR/epoch_0_whole.pt"
echo "GPU eval still holding flock $LOCK"
EVAL_LOG="$LOG_DIR/eval-$(date -u +%Y%m%dT%H%M%SZ).log"
set +e
env \
  PYTHONPATH="$ROOT/packages/shared/src:$COSY:$COSY/third_party/Matcha-TTS" \
  PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF}" \
  CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}" \
  "$PY_CV" "$ROOT/scripts/spark_cosyvoice_khmer_eval.py" \
  --dest "$DEST" \
  --train-dir "$TRAIN_DIR" \
  --dev-dir "$DEV_DIR" \
  --model-src "$MODEL_SRC" \
  --baseline-ckpt "$BASELINE_CKPT" \
  --candidate-ckpt "$CANDIDATE_CKPT" \
  --samples 8 \
  2>&1 | tee "$EVAL_LOG"
EVAL_RC=${PIPESTATUS[0]}
set -e
echo "eval_exit=$EVAL_RC"
if [[ "$EVAL_RC" -ne 0 ]]; then
  tail -n 40 "$EVAL_LOG" >> "$LOG_DIR/last_failure.txt" || true
fi
echo "not promoted (serving config unchanged)"
exit "$EVAL_RC"
