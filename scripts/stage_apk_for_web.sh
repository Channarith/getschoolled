#!/usr/bin/env bash
# Stage the newest signed release APK into apps/web/public/downloads/ so the
# "Get the Salareen app" page can serve it same-origin via /downloads/*.
#
# The APK is 120+ MB — too large to commit (over GitHub's 100 MB file limit) —
# so this script runs BEFORE `docker build apps/web`. The web Dockerfile's
# `COPY apps/web/public /app/public` picks up the staged file and bakes it into
# the image. No object-storage round-trip, no CORS, no fragile proxy.
#
# Usage:
#   ./scripts/stage_apk_for_web.sh                 # pick newest *-release.apk
#   ./scripts/stage_apk_for_web.sh /path/to.apk    # pin a specific file
#
# Emits:
#   apps/web/public/downloads/salareen-latest.apk            (stable URL)
#   apps/web/public/downloads/<original-filename>            (versioned history)
#
# Both are gitignored (see .gitignore block near the bottom of the repo root).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DIR="${REPO_ROOT}/apps/mobile/dist/android"
DEST_DIR="${REPO_ROOT}/apps/web/public/downloads"

mkdir -p "${DEST_DIR}"

if [ "$#" -ge 1 ]; then
  SRC_APK="$1"
else
  # Newest signed release APK in apps/mobile/dist/android/.
  SRC_APK="$(ls -t "${SRC_DIR}"/salareen-*-release.apk 2>/dev/null | head -n 1 || true)"
fi

if [ -z "${SRC_APK:-}" ] || [ ! -f "${SRC_APK}" ]; then
  echo "stage_apk_for_web.sh: no signed APK found." >&2
  echo "  Looked under: ${SRC_DIR}/salareen-*-release.apk" >&2
  echo "  Build one first (apps/mobile) or pass an explicit path." >&2
  exit 1
fi

APK_NAME="$(basename "${SRC_APK}")"
APK_SIZE_MB=$(( $(wc -c < "${SRC_APK}") / 1024 / 1024 ))

echo "Staging APK:   ${SRC_APK}"
echo "               (${APK_SIZE_MB} MB)"
echo "Into:          ${DEST_DIR}/"

cp -f "${SRC_APK}" "${DEST_DIR}/${APK_NAME}"
cp -f "${SRC_APK}" "${DEST_DIR}/salareen-latest.apk"

# Write a tiny manifest the web runtime (and humans) can read to know which
# version is behind /downloads/salareen-latest.apk right now.
cat > "${DEST_DIR}/latest.json" <<EOF
{
  "filename": "${APK_NAME}",
  "staged_at": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "size_bytes": $(wc -c < "${SRC_APK}" | tr -d ' '),
  "sha256": "$(shasum -a 256 "${SRC_APK}" | awk '{print $1}')"
}
EOF

echo "Done. The web app can now serve:"
echo "  /downloads/salareen-latest.apk    (stable)"
echo "  /downloads/${APK_NAME}            (versioned)"
echo "  /downloads/latest.json            (manifest)"
