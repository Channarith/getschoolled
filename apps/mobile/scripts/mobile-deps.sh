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

mobile_deps_has_babel_runtime() {
  local root helper resolved
  root="$(mobile_deps_root)"
  helper="$root/node_modules/@babel/runtime/helpers/interopRequireDefault.js"
  [ -f "$helper" ] || return 1
  resolved="$(cd "$root/node_modules/@babel/runtime" 2>/dev/null && pwd -P)" || return 1
  case "$resolved" in
    "$root"/*) return 0 ;;
    *) return 1 ;;
  esac
}

mobile_deps_has_metro_local_node_modules() {
  local root
  root="$(mobile_deps_root)"
  node "$root/scripts/ensure-metro-local-deps.js" --check 2>/dev/null
}

mobile_deps_ensure_metro_local() {
  local root
  root="$(mobile_deps_root)"
  node "$root/scripts/ensure-metro-local-deps.js"
}

# Back-compat alias used by mobile-expo.sh
mobile_deps_ensure_babel_runtime() {
  mobile_deps_ensure_metro_local
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
    echo "    Metro-local node_modules: $(mobile_deps_has_metro_local_node_modules && echo yes || echo NO — run mobile-expo or mobile-install)"
    echo "    @babel/runtime (Metro-local): $(mobile_deps_has_babel_runtime && echo yes || echo NO)"
  fi
}

mobile_deps_install_hint() {
  echo "  Fix: bash scripts/mobile-install.sh" >&2
  echo "  Or:  rm -rf node_modules && pnpm install --force" >&2
}
