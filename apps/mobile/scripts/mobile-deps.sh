#!/usr/bin/env bash
# Shared dependency checks for apps/mobile bash scripts.
# Source from other scripts:  . "$(dirname "$0")/mobile-deps.sh"

mobile_deps_root() {
  if [ -n "${MOBILE_ROOT:-}" ]; then
    echo "$MOBILE_ROOT"
    return
  fi
  echo "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
}

mobile_deps_has_tsc() {
  [ -e node_modules/.bin/tsc ] || [ -f node_modules/typescript/lib/tsc.js ]
}

mobile_deps_has_expo() {
  [ -e node_modules/.bin/expo ] || [ -f node_modules/expo/bin/cli ] || [ -d node_modules/expo ]
}

mobile_deps_tsc_cmd() {
  if [ -f node_modules/typescript/lib/tsc.js ]; then
    printf '%s\n' node node_modules/typescript/lib/tsc.js
  elif [ -e node_modules/.bin/tsc ]; then
    printf '%s\n' node_modules/.bin/tsc
  else
    return 1
  fi
}

mobile_deps_print_status() {
  echo "    node_modules dir: $([ -d node_modules ] && echo yes || echo NO)"
  if [ -d node_modules ]; then
    echo "    node_modules/.bin/tsc: $([ -e node_modules/.bin/tsc ] && echo yes || echo NO)"
    echo "    typescript/lib/tsc.js: $([ -f node_modules/typescript/lib/tsc.js ] && echo yes || echo NO)"
    echo "    node_modules/.bin/expo: $([ -e node_modules/.bin/expo ] && echo yes || echo NO)"
    echo "    babel-preset-expo: $([ -d node_modules/babel-preset-expo ] && echo yes || echo NO)"
  fi
}

mobile_deps_install_hint() {
  echo "  Fix: bash scripts/mobile-install.sh" >&2
  echo "  Or:  rm -rf node_modules && pnpm install --force" >&2
}
