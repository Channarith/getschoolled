#!/usr/bin/env bash
# Health snapshot for the catalog database VM: writes /var/lib/catalog-db/health.json every 5 minutes
# (and exits non-zero when a threshold is crossed, so `systemctl --failed` and journald show it).
# Thresholds: disk >80% used, >80 connections, newest backup older than 36 h, postgres resident >65% of
# RAM, swap >200 MB, any OOM-kill message in 24 h (critical). Read it from the Mac with: ssh VM cat /var/lib/catalog-db/health.json
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

# memory: resident (PSS, so shared_buffers is not counted once per backend) vs page cache vs the 65% / 90% bands
mem_total_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
mem_avail_kb="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
cache_kb="$(awk '/^(Cached|Buffers):/ {s+=$2} END {print s+0}' /proc/meminfo)"
swap_used_kb="$(awk '/^SwapTotal:/ {t=$2} /^SwapFree:/ {f=$2} END {print t-f}' /proc/meminfo)"
pg_pss_kb=0
for pid in $(pgrep -u postgres 2>/dev/null; pgrep -x pgbouncer 2>/dev/null); do
  v="$(awk '/^Pss:/ {print $2}' "/proc/${pid}/smaps_rollup" 2>/dev/null)"; pg_pss_kb=$(( pg_pss_kb + ${v:-0} ))
done
resident_pct=$(( 100 * pg_pss_kb / mem_total_kb ))
used_incl_cache_pct=$(( 100 * (mem_total_kb - mem_avail_kb) / mem_total_kb ))
cache_pct=$(( 100 * cache_kb / mem_total_kb ))
oom_kills="$(journalctl -k --since '-24 hours' --no-pager 2>/dev/null | grep -ciE 'out of memory|oom-kill|killed process' || true)"
maxwritten="$(psql_q "SELECT maxwritten_clean FROM pg_stat_bgwriter" || echo -1)"
hugepages_free="$(awk '/^HugePages_Free:/ {print $2}' /proc/meminfo)"
hugepages_total="$(awk '/^HugePages_Total:/ {print $2}' /proc/meminfo)"

status=ok; problems=()
[ "${up}" = true ] || { status=critical; problems+=("postgres is not answering"); }
[ "${disk_pct:-0}" -gt 80 ] && { status=warn; problems+=("data disk ${disk_pct}% full"); }
[ "${conns}" -gt 80 ] && { status=warn; problems+=("${conns} connections (max 100)"); }
[ "${resident_pct}" -gt 65 ] && { status=warn; problems+=("postgres resident ${resident_pct}% of RAM (cap 65%)"); }
[ "${used_incl_cache_pct}" -gt 97 ] && { status=warn; problems+=("memory used incl cache ${used_incl_cache_pct}%: little reclaimable cache left"); }
[ "${swap_used_kb}" -gt 204800 ] && { status=warn; problems+=("swap in use: $(( swap_used_kb / 1024 )) MB"); }
[ "${oom_kills}" -gt 0 ] && { status=critical; problems+=("${oom_kills} OOM-kill kernel messages in the last 24 h"); }
[ "${hugepages_total:-0}" -eq 0 ] && problems+=("huge pages not reserved (vm.nr_hugepages=0): shared_buffers uses normal pages")
if [ "${age_h}" -lt 0 ]; then problems+=("no backup found"); [ "${status}" = ok ] && status=warn
elif [ "${age_h}" -gt 36 ]; then status=warn; problems+=("newest backup is ${age_h} h old"); fi

python3 - "$OUT" "$status" "$up" "$disk_pct" "$conns" "$dbsize" "$courses" "$cache_hit" "$age_h" "${problems[*]:-}" \
  "$resident_pct" "$used_incl_cache_pct" "$cache_pct" "$(( swap_used_kb / 1024 ))" "$oom_kills" "$maxwritten" "${hugepages_total:-0}" "${hugepages_free:-0}" <<'EOF'
import json, sys, time
out, status, up, disk, conns, size, courses, hit, age, problems = sys.argv[1:11]
resident, used_cache, cache, swap_mb, ooms, maxw, hp_total, hp_free = sys.argv[11:19]
json.dump({
    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": status, "postgres_up": up == "true",
    "data_disk_pct": int(disk or -1), "connections": int(conns or -1), "database_bytes": int(size or -1),
    "approx_courses": int(courses or -1), "cache_hit_pct": float(hit or -1), "newest_backup_age_hours": int(age),
    "memory": {"postgres_resident_pct_of_ram": int(resident), "used_incl_page_cache_pct": int(used_cache),
               "page_cache_pct": int(cache), "swap_used_mb": int(swap_mb), "oom_kill_messages_24h": int(ooms),
               "bgwriter_maxwritten_clean": int(maxw or -1), "hugepages_total": int(hp_total), "hugepages_free": int(hp_free),
               "bands": "resident <= 65% (cap); resident + page cache ~= 90% (target)"},
    "problems": [p for p in problems.split("  ") if p],
}, open(out, "w"), indent=2)
EOF
[ "${status}" = ok ]
