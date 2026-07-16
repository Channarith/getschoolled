/**
 * Xcode 16.3+ / 26: TARGET_OS_SIMULATOR is not available in Swift.
 * expo-device@6.x (SDK 51) still uses the C macro — use targetEnvironment(simulator).
 */
const fs = require("fs");
const path = require("path");

// Resolve expo-device wherever it actually lives (local copy, pnpm symlink, or
// hoisted to the workspace root) rather than assuming apps/mobile/node_modules.
function resolveExpoDeviceDir() {
  try {
    return path.dirname(
      require.resolve("expo-device/package.json", { paths: [path.join(__dirname, "..")] }),
    );
  } catch {
    const local = path.join(__dirname, "..", "node_modules", "expo-device");
    return fs.existsSync(local) ? local : null;
  }
}

const deviceDir = resolveExpoDeviceDir();
const swiftPath = deviceDir ? path.join(deviceDir, "ios", "UIDevice.swift") : null;

const MARKER = "#if targetEnvironment(simulator)";

const SEARCH = `  var isSimulator: Bool {
    return TARGET_OS_SIMULATOR != 0
  }`;

const REPLACEMENT = `  var isSimulator: Bool {
    #if targetEnvironment(simulator)
    return true
    #else
    return false
    #endif
  }`;

const SEARCH_RE =
  /(\s*)var isSimulator: Bool \{\s*return TARGET_OS_SIMULATOR != 0\s*\}/;

function replacementForMatch(indent) {
  return `${indent}var isSimulator: Bool {
    #if targetEnvironment(simulator)
    return true
    #else
    return false
    #endif
  }`;
}

function main() {
  // expo-device is optional at patch time — if it isn't installed yet, skip
  // cleanly (exit 0) instead of hard-failing the whole native build. The build
  // scripts run mobile_deps_ensure_installed first, so a real build has it.
  if (!swiftPath || !fs.existsSync(swiftPath)) {
    console.log("patch-expo-device-ios: expo-device not installed — skip");
    return;
  }

  let src = fs.readFileSync(swiftPath, "utf8");
  if (src.includes(MARKER)) {
    console.log("patch-expo-device-ios: already patched");
    return;
  }

  if (src.includes(SEARCH)) {
    src = src.replace(SEARCH, REPLACEMENT);
  } else if (SEARCH_RE.test(src)) {
    src = src.replace(SEARCH_RE, (_, indent) => replacementForMatch(indent));
  } else if (!src.includes("TARGET_OS_SIMULATOR")) {
    console.log("patch-expo-device-ios: TARGET_OS_SIMULATOR not present — skip");
    return;
  } else {
    console.error(
      "patch-expo-device-ios: unexpected UIDevice.swift — manual patch required",
    );
    process.exit(1);
  }

  fs.writeFileSync(swiftPath, src);
  console.log("patch-expo-device-ios: replaced TARGET_OS_SIMULATOR in UIDevice.swift");
}

main();
