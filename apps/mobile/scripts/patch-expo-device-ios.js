/**
 * Xcode 16.3+ / 26: TARGET_OS_SIMULATOR is not available in Swift.
 * expo-device@6.x (SDK 51) still uses the C macro — use targetEnvironment(simulator).
 */
const fs = require("fs");
const path = require("path");

const swiftPath = path.join(
  __dirname,
  "..",
  "node_modules",
  "expo-device",
  "ios",
  "UIDevice.swift",
);

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
  if (!fs.existsSync(swiftPath)) {
    console.error("patch-expo-device-ios: expo-device not installed");
    process.exit(1);
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
