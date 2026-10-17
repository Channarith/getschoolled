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
  --metrics-out "$OUT/eval/base.json"

"$PY" training/evaluate.py --offline --device cuda \
  --base-model "$BASE_MODEL" \
  --adapter "$OUT/adapters/stem" \
  --eval "$OUT/data/eval.jsonl" \
  --max-new-tokens 96 \
  --metrics-out "$OUT/eval/stem.json"

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
        },
    })

add("qwen-base", "B", out / "eval" / "base.json")
add("stem-qlora", "B", out / "eval" / "stem.json")

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
if "$PY" training/spark_serve_eval.py \
    --base-url "$SERVE_URL" \
    --model "$SERVE_MODEL" \
    --eval "$OUT/data/eval.jsonl" \
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
  > "$OUT/bakeoff/result.json"

# bakeoff.py prints JSON to stdout, which we redirected. Also show it.
cat "$OUT/bakeoff/result.json"

CHAMPION="$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("champion") or "")' "$OUT/bakeoff/result.json")"
echo "bakeoff_champion=$CHAMPION"
echo "train_seconds=$TRAIN_SEC" | tee "$OUT/train_seconds.txt"

if [[ "$CHAMPION" == "stem-qlora" ]]; then
  echo "== promoting stem-qlora (it won) =="
  "$PY" training/promote.py \
    --candidates "$OUT/bakeoff/candidates.json" \
    --champion-path "$OUT/champion.json" \
    --primary accuracy \
    --max-fairness-gap "$MAX_FAIRNESS_GAP" \
    | tee "$OUT/bakeoff/promote.json"
else
  echo "== stem-qlora did not win; leaving it as a candidate (no promote) =="
  "$PY" - <<PY
import json
from pathlib import Path
out = Path("$OUT")
result = json.loads((out / "bakeoff" / "result.json").read_text(encoding="utf-8"))
note = {
    "promoted": False,
    "candidate": "stem-qlora",
    "adapter": str(out / "adapters" / "stem"),
    "champion": result.get("champion"),
    "reason": "promote only when the STEM adapter wins the bake-off",
}
(out / "candidate.json").write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
print(json.dumps(note))
PY
fi

echo "== done train_seconds=$TRAIN_SEC log=$LOG =="
