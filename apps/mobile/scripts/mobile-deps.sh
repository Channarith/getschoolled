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

mobile_deps_has_drive_mode_packages() {
  [ -d node_modules/expo-location ] && [ -d node_modules/expo-sensors ]
}

# True when the native build stack is actually materialized under
# apps/mobile/node_modules. A bare `pnpm install` can report "Done in <1s"
# without linking anything (pnpm v11 no-op), which leaves react-native / expo
# modules absent — then Android prebuild fails with "libs.versions.toml doesn't
# exist" and iOS patches fail with "<pkg> not installed".
mobile_deps_has_native_stack() {
  local root d
  root="$(mobile_deps_root)"
  [ -f "$root/node_modules/react-native/package.json" ] || return 1
  [ -f "$root/node_modules/react-native/gradle/libs.versions.toml" ] || return 1
  # expo-image-picker is an app.json config plugin — if package.json lists it but
  # node_modules is stale, `expo prebuild` fails with "Failed to resolve plugin".
  for d in expo-asset expo-device expo-localization expo-image-picker; do
    [ -d "$root/node_modules/$d" ] || return 1
  done
  return 0
}

# Guarantee the native dependency tree exists before a native build. If it's
# missing/incomplete, run the robust installer (forces a real copy-linked
# install, working around the pnpm no-op) and re-verify.
mobile_deps_ensure_installed() {
  local root
  root="$(mobile_deps_root)"
  if mobile_deps_has_native_stack; then
    return 0
  fi
  echo "==> apps/mobile native dependencies are missing/incomplete."
  echo "    (a plain 'pnpm install' can no-op without linking — running a forced install)"
  bash "$root/scripts/mobile-install.sh"
  if ! mobile_deps_has_native_stack; then
    echo "ERROR: dependencies still incomplete after install." >&2
    echo "       react-native / expo modules are not present under apps/mobile/node_modules." >&2
    mobile_deps_print_status >&2
    mobile_deps_install_hint
    return 1
  fi
  return 0
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
