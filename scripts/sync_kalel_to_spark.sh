#!/usr/bin/env bash
# One-way handoff from Kal-el (iBuyPower) onto the Spark.
# Copies: CosyVoice download/denoise inbox, small-model adapters, grown train sets.
# Never deletes, never overwrites existing files (rsync --ignore-existing).
#
# On Kal-el:
#   scripts/sync_kalel_to_spark.sh                  # dry-run
#   scripts/sync_kalel_to_spark.sh --yes            # copy
#   SPARK_HOST=nvidia@192.168.1.107 scripts/sync_kalel_to_spark.sh --yes
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
YES=0
SPARK_HOST="${SPARK_HOST:-nvidia@192.168.1.107}"
SPARK_REPO="${SPARK_REPO:-/home/nvidia/code/getschoolled}"

for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
  esac
done

RSYNC=(rsync -ah --partial --info=progress2 --ignore-existing
  --exclude='*.partial' --exclude='*.tmp' --exclude='latest' --exclude='logs/')

run_copy() {
  local src="$1" dest="$2"
  if [[ ! -d "$src" ]]; then
    echo "skip (missing): $src"
    return 0
  fi
  echo "== $src -> ${SPARK_HOST}:$dest =="
  if [[ "$YES" == "1" ]]; then
    "${RSYNC[@]}" "$src"/ "${SPARK_HOST}:$dest"/
  else
    "${RSYNC[@]}" -n "$src"/ "${SPARK_HOST}:$dest"/ || true
    echo "(dry-run; pass --yes to copy)"
  fi
}

run_copy "$ROOT/output/kalel" "$SPARK_REPO/output/inbox/kalel"
# Grown sessions produced on Kal-el (CPU grow-train-set job) land beside Spark data for the next nightly.
if [[ -d "$ROOT/output/kalel/data" ]]; then
  run_copy "$ROOT/output/kalel/data" "$SPARK_REPO/output/spark/data/from-kalel"
fi

echo "done. On Spark, continue CosyVoice with:"
echo "  python3 scripts/cosyvoice_ingest.py --inbox output/inbox/kalel --stages segment,transcribe,export --output-dir output/spark/from-kalel"
exit 0
