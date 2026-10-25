#!/usr/bin/env bash
# Build the fake-camera clips that scripts/mobile_vision_check.mjs feeds to Chromium (--use-file-for-fake-video-capture).
#
#   scripts/mobile_vision_fixtures.sh [--force]
#
# Output: ~/.cache/gs-vision-fixtures (override with GS_VISION_FIXTURES): face_p / face_l (a face), hands_p / hands_l
# (a face and two hands), hands_p_flip (the same, mirrored left-right), in portrait (480x640) and landscape (640x480),
# 10 fps, 5 s, as .y4m.
#
# Sources and licences: the two sample photos come from the MediaPipe sample-asset bucket (the MediaPipe repository
# is Apache-2.0). portrait.jpg is an official US government portrait (public domain as a federal work).
# woman_hands.jpg is a stock photo whose own licence we have not verified. Both are therefore downloaded into a
# local cache for testing and are NEVER committed to this repository. Nobody on the team is used as a test subject.
set -euo pipefail

DEST="${GS_VISION_FIXTURES:-$HOME/.cache/gs-vision-fixtures}"
BASE="https://storage.googleapis.com/mediapipe-assets"
FORCE=0; [[ "${1:-}" == "--force" ]] && FORCE=1
command -v ffmpeg >/dev/null || { echo "ffmpeg is required (brew install ffmpeg)"; exit 1; }
mkdir -p "$DEST"

fetch() {  # name sha256
  local name="$1" want="$2" path="$DEST/$1"
  if [[ ! -s "$path" || $FORCE == 1 ]]; then curl -fsSL --retry 3 -o "$path" "$BASE/$name"; fi
  local got; got="$(shasum -a 256 "$path" | cut -d' ' -f1)"
  [[ "$got" == "$want" ]] || { echo "checksum mismatch for $name: $got (expected $want)"; exit 1; }
}
fetch portrait.jpg a6f11efaa834706db23f275b6115058fa87fc7f14362681e6abe14e82749de3e
fetch woman_hands.jpg 70cbeb38e198c9862202e0979c21a99b40ca980d3e7b250176c85b1636a40f12

clip() {  # out image filter
  local out="$DEST/$1.y4m"
  if [[ -s "$out" && $FORCE == 0 ]]; then return; fi
  ffmpeg -v error -y -loop 1 -t 5 -r 10 -i "$DEST/$2" -vf "$3,format=yuv420p" "$out"
}
clip face_p portrait.jpg "scale=480:640:force_original_aspect_ratio=increase,crop=480:640:0:0"
clip face_l portrait.jpg "scale=640:-2,crop=640:480:0:0"
clip hands_p woman_hands.jpg "scale=480:640:force_original_aspect_ratio=increase,crop=480:640"
clip hands_l woman_hands.jpg "scale=640:-2,crop=640:480:0:240"
clip hands_p_flip woman_hands.jpg "scale=480:640:force_original_aspect_ratio=increase,crop=480:640,hflip"
echo "fixtures ready in $DEST"
ls -1 "$DEST"/*.y4m
