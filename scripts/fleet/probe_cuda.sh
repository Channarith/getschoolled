#!/usr/bin/env bash
# Read-only probe for the CUDA policy: is the GPU idle while the CPU is busy, and does any process carry a CPU pin?
# Runs locally or over `ssh host 'bash -s' < scripts/fleet/probe_cuda.sh`. Never changes anything.
LC_ALL=C
export LC_ALL
echo "CUDA_POLICY_PROBE 1"
echo "host=$(hostname -s 2>/dev/null || hostname)"
echo "cpus=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 0)"
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' %')"
else
  echo "gpu_util=none"
fi
ps -eo pid=,pcpu=,args= --sort=-pcpu 2>/dev/null | head -12 | while read -r pid pcpu args; do
  env_line=""
  if [ -r "/proc/$pid/environ" ]; then
    env_line="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null | grep -E '^(NLLB_DEVICE|AOEP_ASR_DEVICE|AOEP_ALLOW_CPU|AOEP_REQUIRE_CUDA|CUDA_VISIBLE_DEVICES)=' | tr '\n' ' ')"
  fi
  printf 'proc=%s|%s|%s|%s\n' "$pid" "$pcpu" "$(printf '%s' "$args" | cut -c1-160)" "$env_line"
done
