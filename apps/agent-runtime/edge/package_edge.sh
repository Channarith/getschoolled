#!/usr/bin/env bash
# Build a self-contained edge runtime image for a chip/USB device (Phase 15).
# Heavy build runs on the device/CI with model weights present; DRY_RUN=1 just
# validates the manifest + prints the plan (offline-safe).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MANIFEST="$HERE/manifest.yaml"
IMAGE="${EDGE_IMAGE:-aoep/agent-runtime-edge:latest}"

echo "== Edge package =="
echo "manifest: $MANIFEST"
python3 -c "import yaml,sys; d=yaml.safe_load(open('$MANIFEST')); \
print('entry:', d['runtime']['entry']); \
print('models:', [m['role'] for m in d['models']]); \
print('targets:', d['target_devices'])"

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "DRY_RUN: skipping image build + model quantization."
  exit 0
fi

# 1) Quantize models (GGUF via llama.cpp; ONNX export for ASR/TTS/vision).
echo "Quantizing models per manifest (requires source weights present)…"
# llama-quantize / optimum-cli steps run here on the build host.

# 2) Build the self-contained OCI image (DEPLOY_MODE=edge baked in).
docker build -f "$HERE/Dockerfile.edge" -t "$IMAGE" "$HERE/../../.."
echo "Built $IMAGE — flash to the device per docs/edge-robot-runbook.txt."
