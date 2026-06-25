/**
 * Apply native iOS/Android patches after install (local postinstall + EAS hook).
 * EAS iOS runs eas-build-post-install after pod install — patches node_modules
 * immediately before Xcode compiles (postinstall alone is not always enough).
 */
const { spawnSync } = require("child_process");
const path = require("path");

const ROOT = path.join(__dirname, "..");

const PATCHES = [
  { script: "patch-expo-localization-ios.js", required: false },
  { script: "patch-expo-device-ios.js", required: true },
  { script: "patch-react-native-runtimescheduler-ios.js", required: false },
];

function runPatch(script) {
  const scriptPath = path.join(__dirname, script);
  const result = spawnSync(process.execPath, [scriptPath], {
    cwd: ROOT,
    stdio: "inherit",
    env: process.env,
  });
  return result.status === 0;
}

function main() {
  let failedRequired = false;

  for (const { script, required } of PATCHES) {
    const ok = runPatch(script);
    if (!ok) {
      const msg = `mobile-patch-native: ${script} failed`;
      if (required) {
        console.error(msg);
        failedRequired = true;
      } else {
        console.warn(`WARN ${msg} (non-fatal)`);
      }
    }
  }

  // Metro-only; harmless on EAS but not required for native compile.
  runPatch("ensure-metro-local-deps.js");

  if (failedRequired) {
    process.exit(1);
  }
}

main();
