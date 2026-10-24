#!/usr/bin/env bash
# Restore test: prove the newest backup actually restores, without touching the live database.
# Restores the latest dump into a scratch database on the same VM, compares row counts with the
# live catalog, then drops the scratch database. Run it after the first backup and monthly after.
#   sudo catalog-db-restore-test              # latest dump
#   sudo catalog-db-restore-test catalog-20261024T093000Z.dump
set -euo pipefail

source /etc/catalog-db/env
source /etc/catalog-db/secrets.env
export RCLONE_CONFIG_VULTR_TYPE RCLONE_CONFIG_VULTR_PROVIDER RCLONE_CONFIG_VULTR_ENDPOINT \
       RCLONE_CONFIG_VULTR_ACCESS_KEY_ID RCLONE_CONFIG_VULTR_SECRET_ACCESS_KEY

DEST="vultr:${OBJECT_BUCKET}/${OBJECT_PREFIX}/dumps"
NAME="${1:-$(rclone lsf --files-only "${DEST}" | grep '^catalog-.*\.dump$' | sort | tail -1)}"
[ -n "${NAME}" ] || { echo "no dumps found in ${DEST}" >&2; exit 1; }
SCRATCH="catalog_restore_test_$$"

cleanup() { sudo -u postgres dropdb --if-exists "${SCRATCH}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "restore-test: restoring ${NAME} into ${SCRATCH}"
sudo -u postgres createdb "${SCRATCH}"
rclone cat "${DEST}/${NAME}" | sudo -u postgres pg_restore --no-owner -d "${SCRATCH}" --exit-on-error

count() { sudo -u postgres psql -Atd "$1" -c "SELECT count(*) FROM $2"; }
for table in catalog_courses catalog_modules catalog_sources catalog_programs; do
  restored="$(count "${SCRATCH}" "${table}")"
  live="$(count "${CATALOG_DB_NAME}" "${table}")"
  echo "restore-test: ${table}: restored=${restored} live_now=${live}"
  # the live database keeps changing after the dump, so only a restored count of 0 against a non-empty live table is a failure
  if [ "${restored}" -eq 0 ] && [ "${live}" -gt 0 ]; then
    echo "restore-test: FAILED, ${table} restored empty" >&2
    exit 1
  fi
done
sudo -u postgres psql -Atd "${SCRATCH}" -c "SELECT count(*) FROM catalog_courses WHERE fts @@ to_tsquery('simple', 'course')" >/dev/null
echo "restore-test: OK (${NAME} restores and its search index works)"
