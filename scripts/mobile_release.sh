#!/usr/bin/env bash
# mobile_release.sh - native-only mobile release: parity -> build -> verify -> sign check -> publish (-> iOS archive/upload).
#
# POLICY: no EAS / Expo cloud builds (.cursor/rules/no-eas-build-mobile.mdc) and no OTA updates. The JS bundle is embedded
# in every native build, so every UI/JS change reaches users only through a new build. Web pages shown in WebViews (demos,
# labs) update with each web deploy; run `python3 scripts/mobile_release.py staleness` to see how far behind the app is.
#
# Usage:
#   scripts/mobile_release.sh --status                 # staleness + parity only (safe, no build)
#   scripts/mobile_release.sh --android [--publish] [--prune] [--dry-run] [--skip-sign-check]
#   scripts/mobile_release.sh --ios     [--dry-run]
#
# Android publish needs the `aws` CLI configured for Vultr Object Storage (it is S3 compatible). Put the keys in your own
# AWS profile or environment; this script never reads or stores secrets. Defaults:
#   OBJ_ENDPOINT=https://sjc1.vultrobjects.com  OBJ_BUCKET=salareen-prod  OBJ_PREFIX=releases/android
#   PUBLIC_BASE=https://salareen-prod.sjc1.vultrobjects.com   AWS_PROFILE=<your profile>
# The web route /download/android reads ${PUBLIC_BASE}/${OBJ_PREFIX}/latest.json, so publishing latest.json IS the update.
#
# iOS upload needs an App Store Connect API key you create once (App Store Connect > Users and Access > Integrations):
#   ASC_KEY_ID, ASC_ISSUER_ID and the .p8 saved as ~/.appstoreconnect/private_keys/AuthKey_<ASC_KEY_ID>.p8
# Without them the script stops after the .xcarchive and prints the manual Xcode Organizer steps (exit 10).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

OBJ_ENDPOINT="${OBJ_ENDPOINT:-https://sjc1.vultrobjects.com}"
OBJ_BUCKET="${OBJ_BUCKET:-salareen-prod}"
OBJ_PREFIX="${OBJ_PREFIX:-releases/android}"
PUBLIC_BASE="${PUBLIC_BASE:-https://salareen-prod.sjc1.vultrobjects.com}"

DO_ANDROID=0; DO_IOS=0; DO_STATUS=0; DRY=0; PUBLISH=0; PRUNE=0; SKIP_SIGN=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --android) DO_ANDROID=1; shift ;;
    --ios) DO_IOS=1; shift ;;
    --status) DO_STATUS=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --publish) PUBLISH=1; shift ;;
    --prune) PRUNE=1; shift ;;
    --skip-sign-check) SKIP_SIGN=1; shift ;;
    -h|--help) sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done
if [ "${DO_ANDROID}" = "0" ] && [ "${DO_IOS}" = "0" ]; then DO_STATUS=1; fi

log() { printf '[mobile] %s\n' "$*"; }
die() { printf '[mobile] ERROR: %s\n' "$*" >&2; exit 1; }
run() { if [ "${DRY}" = "1" ]; then printf '+ %s\n' "$*"; return 0; fi; "$@"; }

log "== version parity =="
python3 scripts/mobile_release.py parity || die "version files disagree; run scripts/bump_pr_version.py first"

log "== staleness =="
python3 scripts/mobile_release.py staleness || true
[ "${DO_STATUS}" = "1" ] && [ "${DO_ANDROID}" = "0" ] && [ "${DO_IOS}" = "0" ] && exit 0

VERSION_NAME="$(python3 -c "import json;print(json.load(open('apps/mobile/app.json'))['expo']['version'])")"
VERSION_CODE="$(python3 -c "import json;print(json.load(open('apps/mobile/app.json'))['expo'].get('android',{}).get('versionCode',0))")"
GIT_SHA="$(git rev-parse HEAD)"
git diff --quiet && git diff --cached --quiet || die "tracked files have uncommitted changes; a release build must be reproducible from a commit"
log "building v${VERSION_NAME} (versionCode ${VERSION_CODE}) from ${GIT_SHA:0:12}"

if [ "${DO_ANDROID}" = "1" ]; then
  log "== android: native release build (Gradle; bundle embedded) =="
  run bash -c 'cd apps/mobile && pnpm run native:build:android:release'
  APK="${ROOT}/apps/mobile/dist/android/salareen-${VERSION_NAME}-${VERSION_CODE}-release.apk"
  if [ "${DRY}" = "0" ]; then
    [ -f "${APK}" ] || die "expected APK not found: ${APK}"
    bash apps/mobile/scripts/mobile-verify-apk-bundle.sh "${APK}" || die "APK does not embed the JS bundle"
    # Sign check: must verify, and must not be the debug key.
    if [ "${SKIP_SIGN}" = "0" ]; then
      APKSIGNER="$(command -v apksigner || true)"
      if [ -z "${APKSIGNER}" ] && [ -n "${ANDROID_HOME:-}" ]; then
        APKSIGNER="$(ls -1 "${ANDROID_HOME}"/build-tools/*/apksigner 2>/dev/null | sort -V | tail -1 || true)"
      fi
      [ -n "${APKSIGNER}" ] || die "apksigner not found (install Android build-tools or set ANDROID_HOME); or pass --skip-sign-check"
      CERTS="$("${APKSIGNER}" verify --print-certs "${APK}" 2>&1)" || die "apksigner verify failed: ${CERTS}"
      case "${CERTS}" in *"Android Debug"*) die "APK is signed with the DEBUG key" ;; esac
      log "signature ok"
    fi
  else
    echo "+ bash apps/mobile/scripts/mobile-verify-apk-bundle.sh ${APK}"
    echo "+ apksigner verify --print-certs ${APK}   # fail on debug key"
  fi

  if [ "${PUBLISH}" = "1" ]; then
    log "== android: publish to ${OBJ_BUCKET}/${OBJ_PREFIX} =="
    command -v aws >/dev/null 2>&1 || [ "${DRY}" = "1" ] || die "aws CLI not found (needed for S3-compatible Object Storage)"
    KEY="${OBJ_PREFIX}/v${VERSION_NAME}/app-release.apk"
    URL="${PUBLIC_BASE}/${KEY}"
    run aws s3 cp "${APK}" "s3://${OBJ_BUCKET}/${KEY}" --endpoint-url "${OBJ_ENDPOINT}" --acl public-read \
      --content-type application/vnd.android.package-archive --content-disposition attachment
    MANIFEST="${ROOT}/output/train/android-latest.json"
    mkdir -p "${ROOT}/output/train"
    if [ "${DRY}" = "0" ]; then
      python3 scripts/mobile_release.py manifest --apk "${APK}" --url "${URL}" --out "${MANIFEST}" >/dev/null
    else
      echo "+ python3 scripts/mobile_release.py manifest --apk ${APK} --url ${URL} --out ${MANIFEST}"
    fi
    run aws s3 cp "${MANIFEST}" "s3://${OBJ_BUCKET}/${OBJ_PREFIX}/latest.json" --endpoint-url "${OBJ_ENDPOINT}" --acl public-read \
      --content-type application/json --cache-control "max-age=60"
    if [ "${PRUNE}" = "1" ] && [ "${DRY}" = "0" ]; then
      OLD="$(aws s3 ls "s3://${OBJ_BUCKET}/${OBJ_PREFIX}/" --endpoint-url "${OBJ_ENDPOINT}" | awk '/PRE v/ {gsub("/","",$2); print $2}' | python3 scripts/mobile_release.py prune-list --keep 5)"
      for v in ${OLD}; do
        log "pruning old release v${v}"
        aws s3 rm "s3://${OBJ_BUCKET}/${OBJ_PREFIX}/v${v}/" --recursive --endpoint-url "${OBJ_ENDPOINT}"
      done
    fi
    log "published: ${URL} (the site serves it from ${PUBLIC_BASE}/${OBJ_PREFIX}/latest.json within about a minute)"
  else
    log "not publishing (pass --publish). Built: ${APK}"
  fi
fi

if [ "${DO_IOS}" = "1" ]; then
  log "== ios: xcodebuild archive (native; no EAS) =="
  run bash -c 'cd apps/mobile && pnpm run xcode:release'
  ARCHIVE="${ROOT}/apps/mobile/ios/build/Salareen.xcarchive"
  if [ "${DRY}" = "0" ] && [ ! -d "${ARCHIVE}" ]; then die "archive not found: ${ARCHIVE}"; fi
  if [ -n "${ASC_KEY_ID:-}" ] && [ -n "${ASC_ISSUER_ID:-}" ]; then
    EXPORT_DIR="${ROOT}/apps/mobile/ios/build/export"
    PLIST="${ROOT}/apps/mobile/ios/ExportOptions.plist"
    [ -f "${PLIST}" ] || [ "${DRY}" = "1" ] || die "missing ${PLIST} (app-store export options); create it once in Xcode (Product > Archive > Distribute App > export) and commit it"
    run xcodebuild -exportArchive -archivePath "${ARCHIVE}" -exportOptionsPlist "${PLIST}" -exportPath "${EXPORT_DIR}"
    run xcrun altool --upload-app --type ios -f "${EXPORT_DIR}/Salareen.ipa" --apiKey "${ASC_KEY_ID}" --apiIssuer "${ASC_ISSUER_ID}"
    log "uploaded to App Store Connect; the build appears in TestFlight after processing"
  else
    cat <<MSG
[mobile] iOS archive built: ${ARCHIVE}
[mobile] No App Store Connect API key configured, so the upload is a manual step (exit 10):
         1. open "${ARCHIVE}"   (Xcode Organizer)  ->  Distribute App  ->  App Store Connect  ->  Upload
         2. In App Store Connect > TestFlight, wait for processing, then add the build to your testers.
         To automate: create an API key, then export ASC_KEY_ID and ASC_ISSUER_ID and save the .p8 as
         ~/.appstoreconnect/private_keys/AuthKey_<ASC_KEY_ID>.p8, and re-run with --ios.
MSG
    exit 10
  fi
fi
log "done"
