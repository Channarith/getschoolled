#!/usr/bin/env bash
# Create a dedicated venv for the CosyVoice → A2F loop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="${A2F_LOOP_VENV:-$ROOT/.venv}"
SAMPLES="${A2F_SAMPLES:-$HOME/code/Audio2Face-3D-Samples}"
WHEEL="$SAMPLES/proto/sample_wheel/nvidia_ace-1.2.0-py3-none-any.whl"

if [[ ! -f "$WHEEL" ]]; then
  echo "Missing nvidia_ace wheel at $WHEEL" >&2
  echo "Clone: git clone --depth 1 --branch v2.0 https://github.com/NVIDIA/Audio2Face-3D-Samples.git ~/code/Audio2Face-3D-Samples" >&2
  exit 1
fi

python3 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install -U pip
pip install -r "$ROOT/requirements.txt"
pip install "$WHEEL"
echo "Ready: source $VENV/bin/activate"
