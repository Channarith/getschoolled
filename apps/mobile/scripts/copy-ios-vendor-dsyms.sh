#!/usr/bin/env bash
# App Store Connect rejects an upload when the archive has no dSYM for a
# prebuilt framework. hermes and WebRTC ship stripped, so dsymutil writes a
# DWARF file whose UUID matches the embedded binary.
set -euo pipefail

copy_one() {
  local name="$1"
  local bin="$2"
  local dest="$3"
  if [[ ! -f "$bin" ]]; then
    echo "note: ${name} binary missing; skip dSYM"
    return 0
  fi
  local out="${dest}/${name}.framework.dSYM"
  rm -rf "$out"
  echo "note: dSYM for ${name} -> ${out}"
  # The prebuilt binaries are stripped. dsymutil still emits a DWARF file
  # with the binary's UUID, which is what the upload checks. The missing
  # object-file warnings are the original build machine's paths.
  dsymutil "$bin" -o "$out" >/dev/null 2>&1 || true
  if [[ ! -d "$out" ]]; then
    echo "warning: dSYM was not written for ${name}" >&2
    return 1
  fi
}

if [[ -n "${ARCHIVE_PATH:-}" ]]; then
  app="$(find "$ARCHIVE_PATH/Products" -name '*.app' -type d | head -1)"
  if [[ -z "${app}" ]]; then
    echo "note: no .app in ${ARCHIVE_PATH}; skip vendor dSYMs" >&2
    exit 0
  fi
  dest="${ARCHIVE_PATH}/dSYMs"
  mkdir -p "$dest"
  copy_one hermes "${app}/Frameworks/hermes.framework/hermes" "$dest"
  copy_one WebRTC "${app}/Frameworks/WebRTC.framework/WebRTC" "$dest"
  exit 0
fi

if [[ "${ACTION:-}" != "install" ]]; then
  exit 0
fi
dest="${DWARF_DSYM_FOLDER_PATH:-}"
if [[ -z "$dest" ]]; then
  echo "note: DWARF_DSYM_FOLDER_PATH unset; skip vendor dSYMs"
  exit 0
fi
mkdir -p "$dest"
root="${TARGET_BUILD_DIR}/${FRAMEWORKS_FOLDER_PATH}"
copy_one hermes "${root}/hermes.framework/hermes" "$dest"
copy_one WebRTC "${root}/WebRTC.framework/WebRTC" "$dest"
