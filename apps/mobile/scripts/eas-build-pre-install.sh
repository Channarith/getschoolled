#!/usr/bin/env bash
# Runs before EAS `pnpm install`. .npmrc already sets hoisted+copy; export env
# mirrors those flags for workers that ignore local .npmrc.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> eas-build-pre-install (cwd=$ROOT)"

if [[ ! -f .npmrc ]]; then
  echo "ERROR: apps/mobile/.npmrc missing (needs node-linker=hoisted)" >&2
  exit 1
fi

export npm_config_node_linker=hoisted
export npm_config_package_import_method=copy
export npm_config_optimistic_repeat_install=false

echo "    .npmrc present; pnpm will use hoisted+copy layout"
echo "OK eas-build-pre-install"
