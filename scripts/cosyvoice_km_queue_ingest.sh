#!/usr/bin/env bash
# Sequential CosyVoice Khmer ingest over urls/cosyvoice_km/*.txt
# Each channel writes output/cosyvoice_km_<slug>/ and refreshes the merged pool.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

URL_DIR="${COSYVOICE_KM_URL_DIR:-urls/cosyvoice_km}"
SKIP_NEWS="${COSYVOICE_KM_SKIP_NEWS:-1}"
MAX_URLS="${COSYVOICE_KM_MAX_URLS:-}"
REPO="${COSYVOICE_REPO:-/home/nvidia/code/CosyVoice}"

news_slugs='rfi_km rfa_khmer khmerptv vttoday'

for f in "$URL_DIR"/*.txt; do
  [ -f "$f" ] || continue
  slug="$(basename "$f" .txt)"
  if [ "$SKIP_NEWS" = "1" ]; then
    case " $news_slugs " in
      *" $slug "*) echo "skip news (set COSYVOICE_KM_SKIP_NEWS=0 to include): $slug"; continue ;;
    esac
  fi
  out="output/cosyvoice_km_${slug}"
  echo "=== ingest $slug ($(wc -l < "$f") urls) → $out ==="
  args=(
    scripts/cosyvoice_ingest.py
    --urls-file "$f"
    --language km
    --output-dir "$out"
    --cosyvoice-repo "$REPO"
    --speaker "$slug"
  )
  if [ -n "$MAX_URLS" ]; then
    args+=(--max-urls "$MAX_URLS")
  fi
  python3 "${args[@]}" || echo "WARN: $slug exited $?"
done

echo "=== final merge ==="
python3 scripts/cosyvoice_ingest.py --merge-only --language km --merge-scan-root output
echo "Done. Train handoff: output/cosyvoice_km_merged/04_cosyvoice/train/TRAIN_HANDOFF.txt"
