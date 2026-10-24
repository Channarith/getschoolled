#!/usr/bin/env bash
# CUDA policy check for one machine (read-only).
#   scripts/fleet_cuda_check.sh                      # this machine
#   scripts/fleet_cuda_check.sh nvidia@192.168.1.107 # over ssh (key login only)
# Flags: GPU idle while CPU-bound, and processes pinned to CPU (NLLB_DEVICE=cpu, AOEP_ASR_DEVICE=cpu,
# CUDA_VISIBLE_DEVICES empty). Exit 2 on a critical finding.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}"
if [ -n "${1:-}" ]; then
  ssh -o BatchMode=yes -o ConnectTimeout=8 "$1" 'bash -s' < scripts/fleet/probe_cuda.sh | python3 -m aoep_shared.fleet_cuda_policy
else
  bash scripts/fleet/probe_cuda.sh | python3 -m aoep_shared.fleet_cuda_policy
fi
