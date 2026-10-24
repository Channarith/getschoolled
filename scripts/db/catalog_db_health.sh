#!/usr/bin/env bash
# Health snapshot for the catalog database VM: writes /var/lib/catalog-db/health.json every 5 minutes
# (and exits non-zero when a threshold is crossed, so `systemctl --failed` and journald show it).
# Thresholds: disk >80% used, >80 connections, newest backup older than 36 h, a replica-lag-free
# check is not needed (single node). Read it from the Mac with: ssh VM cat /var/lib/catalog-db/health.json
set -uo pipefail

source /etc/catalog-db/env 2>/dev/null || true
source /etc/catalog-db/secrets.env 2>/dev/null || true
export RCLONE_CONFIG_VULTR_TYPE RCLONE_CONFIG_VULTR_PROVIDER RCLONE_CONFIG_VULTR_ENDPOINT \
       RCLONE_CONFIG_VULTR_ACCESS_KEY_ID RCLONE_CONFIG_VULTR_SECRET_ACCESS_KEY

OUT=/var/lib/catalog-db/health.json
mkdir -p "$(dirname "${OUT}")"
psql_q() { sudo -u postgres psql -Atd "${CATALOG_DB_NAME:-catalog}" -c "$1" 2>/dev/null; }

up=false; psql_q "SELECT 1" >/dev/null && up=true
disk_pct="$(df --output=pcent /var/lib/postgresql | tail -1 | tr -dc '0-9')"
conns="$(psql_q "SELECT count(*) FROM pg_stat_activity" || echo -1)"
dbsize="$(psql_q "SELECT pg_database_size(current_database())" || echo -1)"
courses="$(psql_q "SELECT reltuples::bigint FROM pg_class WHERE relname='catalog_courses'" || echo -1)"
cache_hit="$(psql_q "SELECT round(100.0*sum(blks_hit)/nullif(sum(blks_hit)+sum(blks_read),0),2) FROM pg_stat_database WHERE datname=current_database()" || echo -1)"
latest="$(rclone cat "vultr:${OBJECT_BUCKET:-x}/${OBJECT_PREFIX:-x}/dumps/LATEST" 2>/dev/null | awk '{print $1}')"
age_h=-1
if [ -n "${latest}" ]; then
  then_s="$(date -u -d "${latest:0:4}-${latest:4:2}-${latest:6:2} ${latest:9:2}:${latest:11:2}:${latest:13:2}" +%s 2>/dev/null || echo 0)"
  [ "${then_s}" -gt 0 ] && age_h=$(( ( $(date -u +%s) - then_s ) / 3600 ))
fi

status=ok; problems=()
[ "${up}" = true ] || { status=critical; problems+=("postgres is not answering"); }
[ "${disk_pct:-0}" -gt 80 ] && { status=warn; problems+=("data disk ${disk_pct}% full"); }
[ "${conns}" -gt 80 ] && { status=warn; problems+=("${conns} connections (max 100)"); }
if [ "${age_h}" -lt 0 ]; then problems+=("no backup found"); [ "${status}" = ok ] && status=warn
elif [ "${age_h}" -gt 36 ]; then status=warn; problems+=("newest backup is ${age_h} h old"); fi

python3 - "$OUT" "$status" "$up" "$disk_pct" "$conns" "$dbsize" "$courses" "$cache_hit" "$age_h" "${problems[*]:-}" <<'EOF'
import json, sys, time
out, status, up, disk, conns, size, courses, hit, age, problems = sys.argv[1:11]
json.dump({
    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": status, "postgres_up": up == "true",
    "data_disk_pct": int(disk or -1), "connections": int(conns or -1), "database_bytes": int(size or -1),
    "approx_courses": int(courses or -1), "cache_hit_pct": float(hit or -1), "newest_backup_age_hours": int(age),
    "problems": [p for p in problems.split("  ") if p],
}, open(out, "w"), indent=2)
EOF
[ "${status}" = ok ]
