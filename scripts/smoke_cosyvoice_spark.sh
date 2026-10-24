#!/usr/bin/env bash
# Smoke test a REAL CosyVoice server (needs the GPU, so run it on the DGX Spark).
#
#   ./scripts/run_cosyvoice_local.sh &            # start the server (see services/cosyvoice/README.txt)
#   COSYVOICE_URL=http://127.0.0.1:9880 ./scripts/smoke_cosyvoice_spark.sh
#
# Checks /health, then renders a short English sentence in each mode that works
# without a reference voice, validates that the reply is a real WAV, and prints the
# real-time factor (seconds of GPU time per second of audio; below 1.0 is faster
# than real time). It also confirms bad input is a clean 4xx, never a 500.
set -u
URL="${COSYVOICE_URL:-http://127.0.0.1:9880}"
TMP="$(mktemp -d)"
fail=0

echo "== health"
curl -fsS -m 10 "$URL/health" || { echo "server not reachable at $URL"; exit 1; }
echo

render() {
  local label="$1" body="$2" out="$TMP/$1.wav"
  local start end code
  start=$(python3 -c 'import time; print(time.time())')
  code=$(curl -sS -m 300 -o "$out" -w '%{http_code}' -H 'content-type: application/json' -d "$body" "$URL/tts")
  end=$(python3 -c 'import time; print(time.time())')
  python3 - "$label" "$code" "$out" "$start" "$end" <<'PY' || fail=1
import sys, wave
label, code, path, start, end = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
if code != 200:
    print(f"FAIL {label}: HTTP {code}")
    sys.exit(1)
with wave.open(path, "rb") as w:
    seconds = w.getnframes() / w.getframerate()
took = end - start
print(f"ok   {label}: {seconds:.1f}s audio in {took:.1f}s  real-time factor {took / seconds:.2f}")
PY
}

echo "== renders"
render sft_default '{"text":"Welcome to Salareen. Today we are learning about the water cycle."}'
render sft_long    '{"text":"Plants take in sunlight, water and carbon dioxide. They make sugar for energy and release oxygen into the air. This process is called photosynthesis."}'

echo "== bad input must be a clean 4xx"
for body in '{"text":""}' '{"text":"hi","sample_rate":1}' 'not json'; do
  code=$(curl -sS -m 30 -o /dev/null -w '%{http_code}' -H 'content-type: application/json' -d "$body" "$URL/tts")
  case "$code" in 4??) echo "ok   $body -> $code" ;; *) echo "FAIL $body -> $code"; fail=1 ;; esac
done

rm -rf "$TMP"
[ "$fail" = 0 ] && echo "ALL OK" || { echo "SOME CHECKS FAILED"; exit 1; }
