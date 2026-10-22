#!/usr/bin/env bash
# One STEM QLoRA cycle for the Spark host: seed export, train, evaluate,
# bake off against the base and (if up) the local llama-server, promote only
# when the adapter wins the fairness-gated bake-off.
#
# GPU work is wrapped in flock ~/.gs-gpu.lock so it does not overlap other
# jobs that take the same lock. This script does not stop other servers.
#
# Outputs stay under output/spark/ inside the repo (gitignored).
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

if [[ -z "${GS_GPU_LOCK_HELD:-}" ]]; then
  exec flock "${HOME}/.gs-gpu.lock" env GS_GPU_LOCK_HELD=1 "$0" "$@"
fi

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

mkdir -p "$OUT/data" "$OUT/adapters" "$OUT/eval" "$OUT/bakeoff" "$OUT/logs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$OUT/logs/run-${STAMP}.log"
exec > >(tee -a "$LOG") 2>&1

echo "== spark stem cycle $STAMP =="
echo "python=$PY"
echo "base_model=$BASE_MODEL"
echo "out=$OUT"

if [[ ! -d "$BASE_MODEL" ]]; then
  echo "ERROR: BASE_MODEL directory missing: $BASE_MODEL" >&2
  exit 1
fi

echo "== 1/5 seed sessions =="
"$PY" training/spark_seed_sessions.py \
  --curriculum "$ROOT/sample-curriculum" \
  --sample "$ROOT/training/data/sample_sessions.json" \
  --out "$SESSIONS"

echo "== 2/5 export =="
"$PY" training/export.py \
  --in "$SESSIONS" \
  --out "$OUT/data/train.jsonl" \
  --eval-out "$OUT/data/eval.jsonl" \
  --eval-split 0.1

TRAIN_N="$(wc -l < "$OUT/data/train.jsonl" | tr -d ' ')"
EVAL_N="$(wc -l < "$OUT/data/eval.jsonl" | tr -d ' ')"
echo "dataset train=$TRAIN_N eval=$EVAL_N"

echo "== 3/5 QLoRA stem adapter =="
START="$(date +%s)"
"$PY" training/run_finetune.py --offline --device cuda \
  --base-model "$BASE_MODEL" \
  --config "$ROOT/training/config/finetune.spark.yaml" \
  --train "$OUT/data/train.jsonl" \
  --output "$OUT/adapters/stem"
END="$(date +%s)"
TRAIN_SEC="$((END - START))"
echo "train_seconds=$TRAIN_SEC"

echo "== 4/5 evaluate base and adapter =="
"$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" \
  --eval "$OUT/data/eval.jsonl" \
  --max-new-tokens 96 \
  --metrics-out "$OUT/eval/base.json" \
  --truth-log "$OUT/truth_curve.jsonl"

"$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" \
  --adapter "$OUT/adapters/stem" \
  --eval "$OUT/data/eval.jsonl" \
  --max-new-tokens 96 \
  --metrics-out "$OUT/eval/stem.json" \
  --truth-log "$OUT/truth_curve.jsonl"

# The frozen benchmark is never trained on, so it is the score that counts.
FROZEN="${EVAL_FROZEN:-$ROOT/training/data/eval_frozen.jsonl}"
if [[ -f "$FROZEN" ]]; then
  echo "== 4b/5 frozen benchmark ($FROZEN) =="
  "$PY" training/evaluate.py --offline --device cuda \
    --base-model "$BASE_MODEL" \
    --eval "$FROZEN" \
    --max-new-tokens 96 \
    --metrics-out "$OUT/eval/base.frozen.json" \
    --truth-log "$OUT/truth_curve.jsonl"
  "$PY" training/evaluate.py --offline --device cuda \
    --base-model "$BASE_MODEL" \
    --adapter "$OUT/adapters/stem" \
    --eval "$FROZEN" \
    --max-new-tokens 96 \
    --metrics-out "$OUT/eval/stem.frozen.json" \
    --truth-log "$OUT/truth_curve.jsonl"
else
  echo "WARNING: no frozen benchmark at $FROZEN; scoring on the 10% split only." >&2
fi

echo "== 5/5 bake-off =="
"$PY" - <<PY
import json
from pathlib import Path

out = Path("$OUT")
candidates = []

def add(name, track, path):
    metrics = json.loads(Path(path).read_text(encoding="utf-8"))
    candidates.append({
        "name": name,
        "track": track,
        "metrics": {
            "accuracy": float(metrics["accuracy"]),
            "fairness_gap": float(metrics.get("fairness_gap") or 0.0),
            "token_f1": float(metrics.get("token_f1") or metrics["accuracy"]),
            "subject_min": metrics.get("subject_min"),
        },
    })

def best(name):
    frozen = out / "eval" / f"{name}.frozen.json"
    return frozen if frozen.is_file() else out / "eval" / f"{name}.json"

add("qwen-base", "B", best("base"))
add("stem-qlora", "B", best("stem"))

serve_path = out / "eval" / "serving.json"
if serve_path.is_file():
    add("serving-qwen", "serving", serve_path)

(out / "bakeoff" / "candidates.json").write_text(
    json.dumps(candidates, indent=2) + "\n", encoding="utf-8"
)
print(f"wrote {len(candidates)} candidates")
PY

# The live Qwen server is optional. A failure here must not discard the
# adapter eval; the bake-off still compares base vs adapter.
SERVE_EVAL="$OUT/data/eval.jsonl"
if [[ -f "${EVAL_FROZEN:-$ROOT/training/data/eval_frozen.jsonl}" ]]; then
  SERVE_EVAL="${EVAL_FROZEN:-$ROOT/training/data/eval_frozen.jsonl}"
fi
if "$PY" training/spark_serve_eval.py \
    --base-url "$SERVE_URL" \
    --model "$SERVE_MODEL" \
    --eval "$SERVE_EVAL" \
    --metrics-out "$OUT/eval/serving.json"; then
  "$PY" - <<PY
import json
from pathlib import Path
out = Path("$OUT")
path = out / "bakeoff" / "candidates.json"
candidates = json.loads(path.read_text(encoding="utf-8"))
metrics = json.loads((out / "eval" / "serving.json").read_text(encoding="utf-8"))
candidates = [c for c in candidates if c["name"] != "serving-qwen"]
candidates.append({
    "name": "serving-qwen",
    "track": "serving",
    "metrics": {
        "accuracy": float(metrics["accuracy"]),
        "fairness_gap": float(metrics.get("fairness_gap") or 0.0),
        "token_f1": float(metrics.get("token_f1") or metrics["accuracy"]),
    },
})
path.write_text(json.dumps(candidates, indent=2) + "\n", encoding="utf-8")
PY
else
  echo "WARNING: serving-model eval failed; bake-off continues without it"
fi

"$PY" training/bakeoff.py \
  --candidates "$OUT/bakeoff/candidates.json" \
  --primary accuracy \
  --max-fairness-gap "$MAX_FAIRNESS_GAP" \
  --min-subject-score "$MIN_SUBJECT_SCORE" \
  > "$OUT/bakeoff/result.json"

# bakeoff.py prints JSON to stdout, which we redirected. Also show it.
cat "$OUT/bakeoff/result.json"

CHAMPION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("champion") or "")' "$OUT/bakeoff/result.json")"
echo "bakeoff_champion=$CHAMPION"
echo "train_seconds=$TRAIN_SEC" | tee "$OUT/train_seconds.txt"

# Beating the base on a fresh ledger is not progress. Keep the adapter only
# when the frozen-exam score is strictly higher than the last promoted score
# and no sampled subject sits under the floor.
if "$PY" training/promotion_gate.py \
    --name stem-qlora \
    --champion "$CHAMPION" \
    --frozen-metrics "$OUT/eval/stem.frozen.json" \
    --split-metrics "$OUT/eval/stem.json" \
    --previous "$OUT/promoted_frozen.json" \
    --subject-floor "$MIN_SUBJECT_SCORE" \
    --write-promoted "$OUT/promoted_frozen.json" \
    | tee "$OUT/bakeoff/promote.json"; then
  echo "== promoting stem-qlora (frozen score rose and cleared the subject floor) =="
  "$PY" training/promote.py \
    --candidates "$OUT/bakeoff/candidates.json" \
    --champion-path "$OUT/champion.json" \
    --primary accuracy \
    --max-fairness-gap "$MAX_FAIRNESS_GAP" \
    --min-subject-score "$MIN_SUBJECT_SCORE" \
    | tee -a "$OUT/bakeoff/promote.json"
else
  echo "== not promoting; frozen score did not rise or a subject is under the floor =="
fi

echo "== done train_seconds=$TRAIN_SEC log=$LOG =="
