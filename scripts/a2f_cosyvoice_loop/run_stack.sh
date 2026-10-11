#!/usr/bin/env bash
# Start CosyVoice (if needed) + A2F gRPC target + optional orchestrated loop.
#
# On aarch64 Spark the NVIDIA Audio2Face-3D NIM is linux/amd64-only, so the
# default A2F target is the protocol-compatible stub (a2f_stub_server.py).
# Point A2F_GRPC_URL at a real NIM on an x86 GPU host when you have one.
#
# Usage:
#   ./scripts/a2f_cosyvoice_loop/run_stack.sh              # stub + smoke once
#   ./scripts/a2f_cosyvoice_loop/run_stack.sh --loop       # keep feeding phrases
#   ./scripts/a2f_cosyvoice_loop/run_stack.sh --stub-only  # just start stub
#   A2F_USE_NIM=1 ./scripts/a2f_cosyvoice_loop/run_stack.sh  # compose NIM (amd64)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOOP_DIR="$ROOT/scripts/a2f_cosyvoice_loop"
VENV="${A2F_LOOP_VENV:-$LOOP_DIR/.venv}"
SAMPLES="${A2F_SAMPLES:-$HOME/code/Audio2Face-3D-Samples}"
PID_DIR="${A2F_PID_DIR:-/tmp/a2f_cosyvoice_stack}"
mkdir -p "$PID_DIR"

# Load gitignored local secrets / URLs when present.
if [[ -f "$ROOT/config/local.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/config/local.env"
  set +a
fi

export COSYVOICE_URL="${COSYVOICE_URL:-http://127.0.0.1:9880}"
export COSYVOICE_DEFAULT_SPK="${COSYVOICE_DEFAULT_SPK:-英文女}"
export A2F_GRPC_URL="${A2F_GRPC_URL:-127.0.0.1:52000}"
export A2F_GRPC_HOST="${A2F_GRPC_HOST:-0.0.0.0}"
export A2F_GRPC_PORT="${A2F_GRPC_PORT:-52000}"

MODE="smoke"
for arg in "$@"; do
  case "$arg" in
    --loop) MODE="loop" ;;
    --stub-only) MODE="stub-only" ;;
    --help|-h)
      sed -n '2,16p' "$0"
      exit 0
      ;;
  esac
done

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating A2F loop venv…"
  bash "$LOOP_DIR/setup_venv.sh"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

cosy_up() {
  if curl -sf -m 2 "$COSYVOICE_URL/health" >/dev/null 2>&1; then
    echo "CosyVoice already up at $COSYVOICE_URL"
    return 0
  fi
  echo "Starting CosyVoice sidecar…"
  nohup "$ROOT/scripts/run_cosyvoice_local.sh" >"$PID_DIR/cosyvoice.log" 2>&1 &
  echo $! >"$PID_DIR/cosyvoice.pid"
  for _ in $(seq 1 60); do
    if curl -sf -m 2 "$COSYVOICE_URL/health" >/dev/null 2>&1; then
      echo "CosyVoice ready"
      return 0
    fi
    sleep 2
  done
  echo "CosyVoice failed to become ready; see $PID_DIR/cosyvoice.log" >&2
  return 1
}

start_stub() {
  if [[ "${A2F_USE_NIM:-0}" == "1" ]]; then
    echo "A2F_USE_NIM=1 — starting docker compose from $SAMPLES/quick-start"
    if [[ "$(uname -m)" != "x86_64" ]]; then
      echo "WARNING: host is $(uname -m); A2F-3D NIM is linux/amd64-only and will likely fail." >&2
    fi
    if [[ -z "${NGC_API_KEY:-}" ]]; then
      echo "NGC_API_KEY required for NIM pull" >&2
      exit 1
    fi
    echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin
    mkdir -p "$SAMPLES/quick-start/secrets"
    umask 077
    printf '%s' "$NGC_API_KEY" >"$SAMPLES/quick-start/secrets/ngc_api_key"
    (cd "$SAMPLES/quick-start" && docker compose up -d a2f-3d-init a2f-3d-service)
    export A2F_GRPC_URL="${A2F_GRPC_URL:-127.0.0.1:50051}"
    echo "NIM compose started; A2F_GRPC_URL=$A2F_GRPC_URL"
    return 0
  fi

  if [[ -f "$PID_DIR/a2f_stub.pid" ]] && kill -0 "$(cat "$PID_DIR/a2f_stub.pid")" 2>/dev/null; then
    echo "A2F stub already running pid=$(cat "$PID_DIR/a2f_stub.pid")"
    return 0
  fi
  echo "Starting A2F protocol stub on ${A2F_GRPC_HOST}:${A2F_GRPC_PORT}…"
  nohup python "$LOOP_DIR/a2f_stub_server.py" \
    --host "$A2F_GRPC_HOST" --port "$A2F_GRPC_PORT" \
    >"$PID_DIR/a2f_stub.log" 2>&1 &
  echo $! >"$PID_DIR/a2f_stub.pid"
  sleep 1
  echo "A2F stub pid=$(cat "$PID_DIR/a2f_stub.pid") log=$PID_DIR/a2f_stub.log"
}

stop_stack() {
  for name in a2f_stub cosyvoice; do
    if [[ -f "$PID_DIR/$name.pid" ]]; then
      kill "$(cat "$PID_DIR/$name.pid")" 2>/dev/null || true
      rm -f "$PID_DIR/$name.pid"
    fi
  done
}

trap '' HUP

cosy_up
start_stub

if [[ "$MODE" == "stub-only" ]]; then
  echo "Stub/NIM up. CosyVoice=$COSYVOICE_URL A2F=$A2F_GRPC_URL"
  exit 0
fi

if [[ "$MODE" == "loop" ]]; then
  exec python "$LOOP_DIR/cosyvoice_a2f_loop.py" --loop --keep-going --interval "${A2F_LOOP_INTERVAL:-8}"
fi

exec python "$LOOP_DIR/cosyvoice_a2f_loop.py" --once \
  --text "${A2F_SMOKE_TEXT:-Hello from CosyVoice into Audio2Face.}"
