#!/usr/bin/env bash
# Start A2F stub (if needed) + CosyVoice→A2F smoke/loop.
# Real A2F NIM (nvcr.io/nim/nvidia/audio2face-3d) is amd64-only — on Spark we use the stub.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
VENV="${A2F_LOOP_VENV:-$ROOT/.venv}"
LOG_DIR="${A2F_LOOP_LOG_DIR:-/tmp/a2f_cosyvoice_loop}"
mkdir -p "$LOG_DIR"

# Load gitignored local.env if present (NGC keys, COSYVOICE_URL, A2F_GRPC_URL)
if [[ -f "$REPO/config/local.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO/config/local.env"
  set +a
fi

export COSYVOICE_URL="${COSYVOICE_URL:-http://127.0.0.1:9880}"
export COSYVOICE_DEFAULT_SPK="${COSYVOICE_DEFAULT_SPK:-英文女}"
export A2F_GRPC_URL="${A2F_GRPC_URL:-127.0.0.1:52000}"
export A2F_GRPC_PORT="${A2F_GRPC_PORT:-52000}"

if [[ ! -x "$VENV/bin/python" ]]; then
  bash "$ROOT/setup_venv.sh"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# CosyVoice health
if ! curl -fsS -m 3 "$COSYVOICE_URL/health" >/dev/null; then
  echo "CosyVoice not up at $COSYVOICE_URL — starting scripts/run_cosyvoice_local.sh" >&2
  if [[ -x "$REPO/scripts/run_cosyvoice_local.sh" ]]; then
    nohup bash "$REPO/scripts/run_cosyvoice_local.sh" >"$LOG_DIR/cosyvoice.log" 2>&1 &
    echo $! >"$LOG_DIR/cosyvoice.pid"
    for _ in $(seq 1 60); do
      curl -fsS -m 2 "$COSYVOICE_URL/health" >/dev/null 2>&1 && break
      sleep 2
    done
  fi
fi
curl -fsS -m 5 "$COSYVOICE_URL/health" | tee "$LOG_DIR/cosyvoice_health.json"
echo

# A2F: prefer real NIM if already listening; else start stub
A2F_HOST="${A2F_GRPC_URL%:*}"
A2F_PORT="${A2F_GRPC_URL##*:}"
need_stub=1
if "$VENV/bin/python" - <<PY
import asyncio, grpc, sys
from nvidia_ace.health_pb2 import HealthCheckRequest, HealthCheckResponse
from nvidia_ace.health_pb2_grpc import HealthStub
async def main():
    try:
        async with grpc.aio.insecure_channel("${A2F_GRPC_URL}") as ch:
            r = await HealthStub(ch).Check(HealthCheckRequest(), timeout=2)
            sys.exit(0 if r.status == HealthCheckResponse.SERVING else 1)
    except Exception:
        sys.exit(1)
asyncio.run(main())
PY
then
  need_stub=0
  echo "A2F already SERVING at $A2F_GRPC_URL"
fi

if [[ "$need_stub" -eq 1 ]]; then
  # Try official NIM container (will fail on aarch64 — expected)
  if [[ "${A2F_TRY_NIM:-0}" == "1" ]]; then
    echo "Attempting NVIDIA A2F NIM container (amd64)…"
    docker run -d --name a2f-nim \
      --gpus all \
      -e NGC_API_KEY -e NVIDIA_API_KEY \
      -e NIM_HTTP_API_PORT=8000 -e NIM_GRPC_API_PORT=50051 \
      -p 8000:8000 -p 52000:50051 \
      nvcr.io/nim/nvidia/audio2face-3d:1.3 \
      >"$LOG_DIR/a2f_nim_run.txt" 2>&1 || echo "NIM start failed (expected on aarch64); using stub"
  fi
  if ! "$VENV/bin/python" - <<PY
import asyncio, grpc, sys
from nvidia_ace.health_pb2 import HealthCheckRequest, HealthCheckResponse
from nvidia_ace.health_pb2_grpc import HealthStub
async def main():
    try:
        async with grpc.aio.insecure_channel("${A2F_GRPC_URL}") as ch:
            r = await HealthStub(ch).Check(HealthCheckRequest(), timeout=2)
            sys.exit(0 if r.status == HealthCheckResponse.SERVING else 1)
    except Exception:
        sys.exit(1)
asyncio.run(main())
PY
  then
    echo "Starting A2F protocol stub on :$A2F_PORT"
    nohup "$VENV/bin/python" "$ROOT/a2f_stub_server.py" --host 0.0.0.0 --port "$A2F_PORT" \
      >"$LOG_DIR/a2f_stub.log" 2>&1 &
    echo $! >"$LOG_DIR/a2f_stub.pid"
    sleep 1
  fi
fi

MODE="${1:-once}"
shift || true
case "$MODE" in
  once|smoke)
    exec "$VENV/bin/python" "$ROOT/cosyvoice_a2f_loop.py" --once \
      --out-dir "$LOG_DIR/smoke" "$@"
    ;;
  loop)
    nohup "$VENV/bin/python" "$ROOT/cosyvoice_a2f_loop.py" --loop --keep-going \
      --out-dir "$LOG_DIR/smoke" "$@" >"$LOG_DIR/loop.log" 2>&1 &
    echo $! | tee "$LOG_DIR/loop.pid"
    echo "Loop PID $(cat "$LOG_DIR/loop.pid") log=$LOG_DIR/loop.log"
    ;;
  stub-only)
    echo "Stub running pid=$(cat "$LOG_DIR/a2f_stub.pid" 2>/dev/null || echo '?')"
    ;;
  *)
    echo "Usage: $0 {once|smoke|loop|stub-only} [cosyvoice_a2f_loop.py args…]" >&2
    exit 2
    ;;
esac
