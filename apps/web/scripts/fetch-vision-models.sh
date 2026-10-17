#!/usr/bin/env bash
# Fetch YuNet + SFace ONNX weights into apps/web/public/vision-models for local
# `npm run dev` (same URLs as the web Dockerfile; files are gitignored).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/public/vision-models"
YUNET="face_detection_yunet_2023mar.onnx"
SFACE="face_recognition_sface_2021dec.onnx"
mkdir -p "$DEST"
if [[ "${1:-}" == "--check" ]]; then
  test -f "$DEST/$YUNET" && test "$(wc -c < "$DEST/$YUNET" | tr -d ' ')" -gt 150000
  test -f "$DEST/$SFACE" && test "$(wc -c < "$DEST/$SFACE" | tr -d ' ')" -gt 30000000
  echo "vision-models ready"
  exit 0
fi
curl -fsSL --retry 3 -o "$DEST/$YUNET" \
  "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
curl -fsSL --retry 3 -o "$DEST/$SFACE" \
  "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
test "$(wc -c < "$DEST/$YUNET" | tr -d ' ')" -gt 150000
test "$(wc -c < "$DEST/$SFACE" | tr -d ' ')" -gt 30000000
echo "vision-models installed under public/vision-models"
