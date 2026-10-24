#!/usr/bin/env bash
# Nightly logical backup of the catalog database to object storage (Vultr, S3 compatible).
# Streams pg_dump (custom format, compressed) straight to the bucket: no local temp file, so a
# full disk cannot break it. Keeps RETENTION_DAYS of dumps and refuses to delete the newest one.
# Runs on the DB VM (installed as /usr/local/bin/catalog-db-backup by cloud-init); manual run: sudo catalog-db-backup
set -euo pipefail

source /etc/catalog-db/env
source /etc/catalog-db/secrets.env
export RCLONE_CONFIG_VULTR_TYPE RCLONE_CONFIG_VULTR_PROVIDER RCLONE_CONFIG_VULTR_ENDPOINT \
       RCLONE_CONFIG_VULTR_ACCESS_KEY_ID RCLONE_CONFIG_VULTR_SECRET_ACCESS_KEY

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="vultr:${OBJECT_BUCKET}/${OBJECT_PREFIX}/dumps"
NAME="catalog-${STAMP}.dump"

echo "backup: starting ${NAME}"
sudo -u postgres pg_dump -Fc -Z 6 --no-owner "${CATALOG_DB_NAME}" \
  | rclone rcat --s3-no-check-bucket "${DEST}/${NAME}"

SIZE="$(rclone size --json "${DEST}/${NAME}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["bytes"])')"
if [ "${SIZE}" -lt 10000 ]; then
  echo "backup: ${NAME} is only ${SIZE} bytes: something is wrong, keeping older dumps untouched" >&2
  exit 1
fi
echo "backup: ${NAME} stored (${SIZE} bytes)"
echo "${STAMP} ${SIZE}" | rclone rcat --s3-no-check-bucket "${DEST}/LATEST"

# retention: delete dumps older than RETENTION_DAYS but always keep the newest three
mapfile -t OLD < <(rclone lsf --files-only --min-age "${RETENTION_DAYS}d" "${DEST}" | grep '^catalog-.*\.dump$' | sort)
mapfile -t ALL < <(rclone lsf --files-only "${DEST}" | grep '^catalog-.*\.dump$' | sort)
KEEP_NEWEST="$(printf '%s\n' "${ALL[@]}" | tail -3)"
for f in "${OLD[@]:-}"; do
  [ -z "${f}" ] && continue
  if grep -qx "${f}" <<<"${KEEP_NEWEST}"; then continue; fi
  rclone deletefile "${DEST}/${f}" && echo "backup: removed old ${f}"
done
