#!/usr/bin/env bash
# Track B - train one QLoRA adapter per domain over the open-weight base.
# Heavy run -> execute on the GPU agent (see training/RUNBOOK.txt). Offline-safe
# dry run: DRY_RUN=1 ./training/base/train_adapters.sh
set -euo pipefail

TRAIN="${1:-train.jsonl}"
OUT="${ADAPTER_DIR:-adapters}"
DOMAINS="${DOMAINS:-stem humanities languages vocational}"   # medical is safety-gated
: "${BASE_MODEL:?set BASE_MODEL (open-weight base checkpoint or HF id)}"

for d in $DOMAINS; do
  echo "== fine-tuning Track B adapter: $d -> $OUT/$d =="
  if [ "${DRY_RUN:-0}" = "1" ]; then
    python3 training/run_finetune.py --check --base-model "$BASE_MODEL" \
      --train "$TRAIN" --output "$OUT/$d"
  else
    python3 training/run_finetune.py --offline --base-model "$BASE_MODEL" \
      --train "$TRAIN" --output "$OUT/$d"
  fi
done
echo "Adapters ready in $OUT. Generate LLM_ROUTES: python3 training/base/routes.py"
