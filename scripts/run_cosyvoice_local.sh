#!/usr/bin/env bash
# Start the AOEP CosyVoice /tts sidecar against a native CosyVoice checkout.
# Prefer this on NVIDIA Spark / aarch64 — Docker Desktop has no host GPU CDI.
#
# Usage:
#   ./scripts/run_cosyvoice_local.sh
#   COSYVOICE_REPO=~/code/CosyVoice COSYVOICE_MODEL_DIR=... ./scripts/run_cosyvoice_local.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COSYVOICE_REPO="${COSYVOICE_REPO:-$HOME/code/CosyVoice}"
VENV="${COSYVOICE_VENV:-$COSYVOICE_REPO/.venv}"
MODEL_DIR="${COSYVOICE_MODEL_DIR:-$COSYVOICE_REPO/pretrained_models/CosyVoice-300M-SFT}"
PORT="${COSYVOICE_PORT:-9880}"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "CosyVoice venv missing at $VENV" >&2
  echo "Create it (Spark/GB10): python3 -m venv $COSYVOICE_REPO/.venv && pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130" >&2
  exit 1
fi
if [[ ! -d "$MODEL_DIR" ]]; then
  echo "Model dir missing: $MODEL_DIR" >&2
  echo "Download e.g. FunAudioLLM/CosyVoice-300M-SFT into pretrained_models/" >&2
  exit 1
fi
if [[ ! -d "$COSYVOICE_REPO/third_party/Matcha-TTS/matcha" ]]; then
  echo "Matcha-TTS submodule missing — run: git -C $COSYVOICE_REPO submodule update --init --recursive" >&2
  exit 1
fi

export COSYVOICE_MODEL_DIR="$MODEL_DIR"
export COSYVOICE_PORT="$PORT"
export COSYVOICE_USE_VLLM="${COSYVOICE_USE_VLLM:-0}"
export COSYVOICE_FP16="${COSYVOICE_FP16:-1}"
export COSYVOICE_DEFAULT_SPK="${COSYVOICE_DEFAULT_SPK:-英文女}"
export PYTHONPATH="$COSYVOICE_REPO:$COSYVOICE_REPO/third_party/Matcha-TTS:${PYTHONPATH:-}"

echo "CosyVoice sidecar on :$PORT  model=$MODEL_DIR  vllm=$COSYVOICE_USE_VLLM"
exec "$VENV/bin/python" "$ROOT/services/cosyvoice/server.py"
