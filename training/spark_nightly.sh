#!/usr/bin/env bash
# One tutor QLoRA cycle for the Spark host: seed + tutor sessions, quality gate, export, train,
# evaluate base and adapter on every benchmark, bake off, promote only when ALL of these hold:
#   1. the adapter wins the fairness-, subject-floor- and behaviour-gated bake-off
#      (abstain/refuse/hint accuracy must not regress against the base), AND
#   2. its frozen-exam score is strictly higher than the last promoted score (training/promotion_gate.py), AND
#   3. no sampled subject on the frozen, STEM-frozen or split exams sits under MIN_SUBJECT_SCORE.
# A repeated win over the base on an unchanged adapter is not progress and is never kept.
#
# Safe by construction:
#   - holds ~/.gs-gpu.lock (waits up to GS_LOCK_WAIT_SEC, then exits 75; never two GPU jobs at once);
#   - every long stage runs under training/lib_limits.sh (RAM ceiling, CPU quota, timeout, own process
#     group, free-RAM watchdog) so it cannot starve the machine or leave orphans behind;
#   - refuses to start when free RAM is below the reserve plus what the stage needs;
#   - does not stop other servers.
#
# Outputs stay under output/spark/ inside the repo (gitignored).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

if [[ -z "${GS_GPU_LOCK_HELD:-}" ]]; then
  exec flock -w "${GS_LOCK_WAIT_SEC:-7200}" "${HOME}/.gs-gpu.lock" env GS_GPU_LOCK_HELD=1 "$0" "$@"
fi

# shellcheck source=training/lib_limits.sh
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

OUT="${SPARK_OUT:-$ROOT/output/spark}"
BASE_MODEL="${BASE_MODEL:-$ROOT/models/weights/qwen2.5-7b-instruct}"
SESSIONS="${SESSIONS:-$OUT/data/sessions.json}"
SERVE_URL="${SERVE_URL:-http://127.0.0.1:8342/v1}"
SERVE_MODEL="${SERVE_MODEL:-qwen3.6-35b-a3b}"
MAX_FAIRNESS_GAP="${MAX_FAIRNESS_GAP:-0.1}"
MIN_SUBJECT_SCORE="${MIN_SUBJECT_SCORE:-0.40}"
NEED_GB="${NEED_GB:-24}"                  # free RAM a 7B-14B QLoRA cycle needs on top of the reserve
TRAIN_TIMEOUT_MIN="${TRAIN_TIMEOUT_MIN:-300}"
EVAL_TIMEOUT_MIN="${EVAL_TIMEOUT_MIN:-120}"

mkdir -p "$OUT/data" "$OUT/adapters" "$OUT/eval" "$OUT/bakeoff" "$OUT/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$OUT/logs/run-${STAMP}.log"
exec > >(tee -a "$LOG") 2>&1

echo "== spark tutor cycle $STAMP =="
echo "python=$PY"
echo "base_model=$BASE_MODEL"
echo "out=$OUT"

if [[ ! -d "$BASE_MODEL" ]]; then
  echo "ERROR: BASE_MODEL directory missing: $BASE_MODEL" >&2
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
if [[ ! -f "${EVAL_FROZEN:-$ROOT/training/data/eval_frozen.jsonl}" ]]; then
  echo "WARNING: no frozen benchmark; scoring on the 10% split only." >&2
fi
if [[ ! -f "${EVAL_FROZEN_STEM:-$ROOT/training/data/eval_frozen_stem.jsonl}" ]]; then
  echo "WARNING: no STEM frozen exam; subjects like linear algebra are not gated." >&2
fi

echo "== 1/6 seed + tutor sessions =="
"$PY" training/spark_seed_sessions.py \
  --curriculum "$ROOT/sample-curriculum" \
  --sample "$ROOT/training/data/sample_sessions.json" \
  --out "$SESSIONS"
"$PY" training/tutor_sessions.py --curriculum "$ROOT/sample-curriculum" --out "$OUT/data/tutor_sessions.json"

echo "== 2/6 data-quality gate (dedupe, PII, consent, language, protected attributes) =="
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

echo "== 4/6 QLoRA adapter =="
START="$(date +%s)"
gs_stage "train" "$TRAIN_TIMEOUT_MIN" "$PY" training/run_finetune.py --offline --device cuda \
  --base-model "$BASE_MODEL" \
  --config "$ROOT/training/config/finetune.spark.yaml" \
  --train "$OUT/data/train.jsonl" \
  --output "$OUT/adapters/stem"
END="$(date +%s)"
TRAIN_SEC="$((END - START))"
echo "train_seconds=$TRAIN_SEC"

echo "== 5/6 evaluate base and adapter on every benchmark =="
EXISTING=()
for f in "${BENCHMARKS[@]}"; do [[ -f "$f" ]] && EXISTING+=("$f"); done
gs_stage "eval-base" "$EVAL_TIMEOUT_MIN" "$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" --max-new-tokens 96 \
  --metrics-dir "$OUT/eval/base" --truth-log "$OUT/truth_curve.jsonl" --eval "${EXISTING[@]}"
gs_stage "eval-adapter" "$EVAL_TIMEOUT_MIN" "$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" --adapter "$OUT/adapters/stem" --max-new-tokens 96 \
  --metrics-dir "$OUT/eval/stem" --truth-log "$OUT/truth_curve.jsonl" --eval "${EXISTING[@]}"

echo "== 6/6 bake-off =="
"$PY" training/nightly_candidates.py --out "$OUT" --serve-url "$SERVE_URL" --serve-model "$SERVE_MODEL" \
  --max-fairness-gap "$MAX_FAIRNESS_GAP" --min-subject-score "$MIN_SUBJECT_SCORE"

CHAMPION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("champion") or "")' "$OUT/bakeoff/result.json")"
echo "bakeoff_champion=$CHAMPION"
echo "train_seconds=$TRAIN_SEC" | tee "$OUT/train_seconds.txt"

# Gate 1 (bake-off) already ran. Gate 2 and 3: strictly higher frozen score than the last promoted
# adapter and every sampled subject at or above the floor. Both must pass.
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
  echo "== promoting stem-qlora (won the bake-off, frozen score rose, every subject cleared the floor) =="
  # shellcheck disable=SC2046
  "$PY" training/promote.py \
    --candidates "$OUT/bakeoff/candidates.json" \
    --champion-path "$OUT/champion.json" \
    --primary accuracy \
    --max-fairness-gap "$MAX_FAIRNESS_GAP" \
    $(cat "$OUT/bakeoff/floors.args") \
    | tee "$OUT/bakeoff/promote.json"
else
  echo "== not promoting stem-qlora (bake-off, frozen-score rise, or subject floor not met); kept as a candidate =="
  "$PY" training/nightly_candidates.py --out "$OUT" --note-only
fi

echo "== done train_seconds=$TRAIN_SEC log=$LOG =="
"$PY" training/frontier_readiness.py --record --spark-out "$OUT" \
  || echo "WARNING: frontier readiness report failed"
