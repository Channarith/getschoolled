#!/usr/bin/env bash
# One tutor QLoRA cycle for Kal-el (iBuyPower, RTX 5060 Ti 8 GB): seed + tutor sessions,
# quality gate, export, train a SMALL base (<=4B), evaluate base and adapter, bake off,
# promote only when the same three gates as the Spark nightly pass.
#
# Why this machine: the Spark owns 7B-14B fine-tunes and CosyVoice ASR. Kal-el owns a
# parallel small-model track so frontier progress is not blocked on one GPU. Outputs stay
# under output/kalel/ (gitignored). Sync winners to the Spark with scripts/sync_kalel_to_spark.sh.
#
# Safe by construction: same hold file / GPU lock / lib_limits pattern as spark_nightly.sh.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

HOLD_FILE="${GS_KALEL_HOLD_FILE:-${HOME}/.gs-hold/kalel-train}"
if [[ -e "$HOLD_FILE" ]]; then
  echo "kalel_nightly: paused by hold file $HOLD_FILE ($(head -c 200 "$HOLD_FILE" 2>/dev/null | tr '\n' ' ')); not starting a cycle" >&2
  exit 0
fi

if [[ -z "${GS_GPU_LOCK_HELD:-}" ]]; then
  exec flock -w "${GS_LOCK_WAIT_SEC:-7200}" "${HOME}/.gs-gpu.lock" env GS_GPU_LOCK_HELD=1 GS_NIGHTLY_OWNS_LOCK=1 "$0" "$@"
fi
if [[ -n "${GS_NIGHTLY_OWNS_LOCK:-}" ]]; then
  printf '%s %s %s %s %s\n' "$$" "kalel-nightly-$(date +%Y%m%d)" "kalel_nightly" "$(date +%s)" background > "${HOME}/.gs-gpu.lock.owner" 2>/dev/null || true
fi

# shellcheck source=training/lib_limits.sh
export GS_PROFILE="${GS_PROFILE:-ibuypower}"
. "$ROOT/training/lib_limits.sh"

export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

OUT="${KALEL_OUT:-$ROOT/output/kalel}"
BASE_MODEL="${BASE_MODEL:-$ROOT/models/weights/llama-3.2-3b-instruct}"
SESSIONS="${SESSIONS:-$OUT/data/sessions.json}"
MAX_FAIRNESS_GAP="${MAX_FAIRNESS_GAP:-0.1}"
MIN_SUBJECT_SCORE="${MIN_SUBJECT_SCORE:-0.40}"
NEED_GB="${NEED_GB:-8}"
TRAIN_TIMEOUT_MIN="${TRAIN_TIMEOUT_MIN:-240}"
EVAL_TIMEOUT_MIN="${EVAL_TIMEOUT_MIN:-90}"
BAKEOFF_TIMEOUT_MIN="${BAKEOFF_TIMEOUT_MIN:-30}"

mkdir -p "$OUT/data" "$OUT/adapters" "$OUT/eval" "$OUT/bakeoff" "$OUT/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$OUT/logs/run-${STAMP}.log"
exec > >(tee -a "$LOG") 2>&1

echo "== kalel tutor cycle $STAMP =="
if ! PYTHONPATH="$ROOT/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}" "$PY" -c \
  "from aoep_shared.devices import pick_device; print('device policy ok:', pick_device('kalel-nightly', 'cuda'))"; then
  echo "ERROR: CUDA is preferred for the Kal-el nightly and is not usable; nothing was started." >&2
  exit 3
fi
echo "python=$PY"
echo "base_model=$BASE_MODEL"
echo "out=$OUT"

if [[ ! -d "$BASE_MODEL" ]]; then
  echo "ERROR: BASE_MODEL directory missing: $BASE_MODEL (download a <=4B instruct model first)" >&2
  exit 1
fi
gs_preflight "$NEED_GB" || exit $?

BENCHMARKS=(
  "$OUT/data/eval.jsonl"
  "${EVAL_FROZEN:-$ROOT/training/data/eval_frozen.jsonl}"
  "${EVAL_FROZEN_STEM:-$ROOT/training/data/eval_frozen_stem.jsonl}"
  "$ROOT/training/data/eval_behavior_v1.jsonl"
  "$ROOT/training/data/eval_multilingual_v1.jsonl"
)

echo "== 1/6 seed + tutor sessions =="
"$PY" training/spark_seed_sessions.py \
  --curriculum "$ROOT/sample-curriculum" \
  --sample "$ROOT/training/data/sample_sessions.json" \
  --out "$SESSIONS"
"$PY" training/tutor_sessions.py --curriculum "$ROOT/sample-curriculum" --out "$OUT/data/tutor_sessions.json"

echo "== 2/6 data-quality gate =="
"$PY" training/quality_gate.py \
  --in "$SESSIONS" "$OUT/data/tutor_sessions.json" \
  --out "$OUT/data/sessions.clean.json" \
  --report "$OUT/data/quality.json"

echo "== 3/6 export =="
"$PY" training/export.py \
  --in "$OUT/data/sessions.clean.json" \
  --out "$OUT/data/train.jsonl" \
  --eval-out "$OUT/data/eval.jsonl" \
  --eval-split 0.1

TRAIN_N="$(wc -l < "$OUT/data/train.jsonl" | tr -d ' ')"
EVAL_N="$(wc -l < "$OUT/data/eval.jsonl" | tr -d ' ')"
echo "dataset train=$TRAIN_N eval=$EVAL_N"

echo "== 4/6 QLoRA adapter (Kal-el 8 GB config) =="
START="$(date +%s)"
gs_stage "train" "$TRAIN_TIMEOUT_MIN" "$PY" training/run_finetune.py --offline --device cuda \
  --base-model "$BASE_MODEL" \
  --config "$ROOT/training/config/finetune.kalel.yaml" \
  --train "$OUT/data/train.jsonl" \
  --output "$OUT/adapters/stem"
END="$(date +%s)"
TRAIN_SEC="$((END - START))"
echo "train_seconds=$TRAIN_SEC"

echo "== 5/6 evaluate base and adapter (4-bit load when needed) =="
EXISTING=()
for f in "${BENCHMARKS[@]}"; do [[ -f "$f" ]] && EXISTING+=("$f"); done
# Small VRAM: prefer 4-bit load for eval of the base when KALEL_LOAD_4BIT=1 (default).
LOAD4=()
if [[ "${KALEL_LOAD_4BIT:-1}" == "1" ]]; then
  LOAD4=(--load-4bit)
fi
gs_stage "eval-base" "$EVAL_TIMEOUT_MIN" "$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" --max-new-tokens 96 "${LOAD4[@]}" \
  --metrics-dir "$OUT/eval/base" --truth-log "$OUT/truth_curve.jsonl" --eval "${EXISTING[@]}"
gs_stage "eval-adapter" "$EVAL_TIMEOUT_MIN" "$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" --adapter "$OUT/adapters/stem" --max-new-tokens 96 "${LOAD4[@]}" \
  --metrics-dir "$OUT/eval/stem" --truth-log "$OUT/truth_curve.jsonl" --eval "${EXISTING[@]}"

echo "== 6/6 bake-off (no live 35B server on Kal-el) =="
gs_stage "bakeoff" "$BAKEOFF_TIMEOUT_MIN" "$PY" training/nightly_candidates.py \
  --out "$OUT" --serve-url "" --serve-model "" \
  --max-fairness-gap "$MAX_FAIRNESS_GAP" --min-subject-score "$MIN_SUBJECT_SCORE"

CHAMPION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("champion") or "")' "$OUT/bakeoff/result.json")"
echo "bakeoff_champion=$CHAMPION"
echo "train_seconds=$TRAIN_SEC" | tee "$OUT/train_seconds.txt"

GATE_OK=0
if [[ "$CHAMPION" == "stem-qlora" ]]; then
  STEM_ARGS=()
  [[ -f "$OUT/eval/stem.stemfrozen.json" ]] && STEM_ARGS=(--stem-metrics "$OUT/eval/stem.stemfrozen.json")
  if "$PY" training/promotion_gate.py \
      --name stem-qlora \
      --champion "$CHAMPION" \
      --frozen-metrics "$OUT/eval/stem.frozen.json" \
      --split-metrics "$OUT/eval/stem.json" \
      --previous "$OUT/promoted_frozen.json" \
      --subject-floor "$MIN_SUBJECT_SCORE" \
      --min-subject-n 1 \
      ${STEM_ARGS[@]+"${STEM_ARGS[@]}"} \
      --write-promoted "$OUT/promoted_frozen.json" \
      | tee "$OUT/bakeoff/promote_gate.json"; then
    GATE_OK=1
  fi
fi

if [[ "$GATE_OK" == "1" ]]; then
  echo "== promoting stem-qlora on Kal-el (sync to Spark with scripts/sync_kalel_to_spark.sh) =="
  # shellcheck disable=SC2046
  "$PY" training/promote.py \
    --candidates "$OUT/bakeoff/candidates.json" \
    --champion-path "$OUT/champion.json" \
    --primary accuracy \
    --max-fairness-gap "$MAX_FAIRNESS_GAP" \
    $(cat "$OUT/bakeoff/floors.args") \
    | tee "$OUT/bakeoff/promote.json"
else
  echo "== not promoting; kept as a candidate under output/kalel/ =="
  "$PY" training/nightly_candidates.py --out "$OUT" --note-only
fi

echo "== done train_seconds=$TRAIN_SEC log=$LOG =="
"$PY" training/frontier_readiness.py --record --spark-out "$OUT" \
  || echo "WARNING: frontier readiness report failed"
