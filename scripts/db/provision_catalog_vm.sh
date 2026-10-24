#!/usr/bin/env bash
# Provision the catalog database VM on Vultr (outside the broken cluster, same region, private VPC).
# DRY RUN by default: prints the exact API request and the monthly cost from Vultr's current prices.
#
#   export VULTR_API_KEY=...
#   scripts/db/provision_catalog_vm.sh --admin-cidr "$(curl -s https://ifconfig.me)/32"           # dry run
#   OBJECT_STORE_ACCESS_KEY=... OBJECT_STORE_SECRET_KEY=... \
#     scripts/db/provision_catalog_vm.sh --admin-cidr 203.0.113.7/32 --apply                      # creates it
#
# Options are documented in provision_catalog_vm.py (--plan, --region, --vpc-id, --ssh-key-id,
# --no-backups, --wal-archive). Nothing here runs without --apply, and a second run never makes a second VM.
set -euo pipefail
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/provision_catalog_vm.py" "$@"
