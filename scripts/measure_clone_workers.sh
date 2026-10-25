#!/usr/bin/env bash
# Measure whether --workers N is faster on THIS machine (run on the Spark): the same fixed set of clips for each N, fresh output folders,
# under gs_run.sh like a real run (GPU lock, memory gate). A single GPU may give little or no gain from N > 1: this says by how much.
#
#   scripts/measure_clone_workers.sh [N ...]          default: 1 2 3
#   SPEAKERS=channarith,wei-miao  MODEL=voxcpm2  LANGS=en,es,zh,vi,th,km,sw,hi  LIMIT=2   (defaults shown except SPEAKERS = all enrolled)
# Output: workers, seconds, clips made, clips/min, speedup against N=1. The test clips go to a temp folder and are deleted afterwards.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NS=("$@"); [[ ${#NS[@]} -gt 0 ]] || NS=(1 2 3)
MODEL="${MODEL:-voxcpm2}"; LANGS="${LANGS:-en,es,zh,vi,th,km,sw,hi}"; LIMIT="${LIMIT:-2}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/clone-measure.XXXXXX")"; trap 'rm -rf "$TMP"' EXIT
base_secs=""
printf '%-8s %-9s %-7s %-11s %s\n' workers seconds clips clips/min speedup
for n in "${NS[@]}"; do
  out="$TMP/n$n"; start=$(date +%s)
  MODELS="$MODEL" LANGS="$LANGS" GS_CLONE_WORKERS="$n" "$ROOT/scripts/run_voice_clone.sh" "$out" --force --limit "$LIMIT" --takes 1 ${SPEAKERS:+--speakers "$SPEAKERS"} >"$TMP/n$n.log" 2>&1 || { echo "run with $n workers failed; see $TMP/n$n.log"; trap - EXIT; exit 1; }
  secs=$(( $(date +%s) - start )); clips=$(find "$out" -name '*.wav' -not -path '*/.raw/*' -not -path '*/.take*' | wc -l)
  [[ -n "$base_secs" ]] || base_secs=$secs
  awk -v n="$n" -v s="$secs" -v c="$clips" -v b="$base_secs" 'BEGIN{printf "%-8s %-9s %-7s %-11.1f %.2fx\n", n, s, c, (s>0? c*60/s : 0), (s>0? b/s : 0)}'
done
