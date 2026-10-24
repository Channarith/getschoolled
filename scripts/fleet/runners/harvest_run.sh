#!/usr/bin/env bash
# One shard of the license-gated crawl: refuse unsafe license settings, take this shard's seeds, crawl.
#   harvest_run.sh SHARD NSHARDS PER_HOUR
# Exit 78 = configuration problem (the queue does not retry it).
set -euo pipefail
cd "$(dirname "$0")/../../.."
shard="${1:?shard}"; nshards="${2:?nshards}"; per_hour="${3:?per_hour}"
PY="${GS_PYTHON:-python3}"
export PYTHONPATH="$PWD/packages/shared/src:${PYTHONPATH:-}"

# Salareen is a commercial product. Non-commercial licenses (cc-by-nc, cc-by-nc-sa) must not be harvested
# into it. Refuse to run while the allowlist still contains one, unless someone overrides on purpose.
if [ "${GS_ALLOW_NC:-0}" != "1" ]; then
  nc="$("$PY" -c 'from aoep_shared.harvest.sources import LICENSE_ALLOWLIST as L; print(",".join(sorted(x for x in L if "-nc" in x)))')" || exit 78
  if [ -n "$nc" ]; then
    echo "harvest_run: the license allowlist still allows NON-COMMERCIAL licenses ($nc). Refusing to crawl for a" \
         "commercial product. Fix aoep_shared/harvest/sources.py, or set GS_ALLOW_NC=1 for an internal research crawl." >&2
    exit 78
  fi
fi

seeds="${HARVEST_SEEDS:-$HOME/.config/gs/harvest-seeds.jsonl}"
out="${GS_STATE_DIR:-$HOME/.gs-queue}/work/harvest/seeds-${shard}-of-${nshards}.jsonl"
"$PY" scripts/fleet/shard_seeds.py --seeds "$seeds" --shard "$shard" --of "$nshards" --out "$out" || exit $?
export HARVEST_USER_AGENT="${HARVEST_USER_AGENT:-SalareenHarvester/1.0 (contact: ops@salareen.com)}"
export HARVEST_MAX_RPS="${HARVEST_MAX_RPS:-1}"
exec "$PY" services/harvester/src/harvester/run.py --crawl --seeds "$out" --daemon \
  --per-hour "$per_hour" --max-hours 6 --interval 45
