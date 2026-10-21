/**
 * Apply native iOS/Android patches after install (local postinstall hook).
 * Runs via `pnpm install` postinstall so node_modules are patched before any
 * local Gradle/Xcode build (postinstall alone is not always enough on iOS, so
 * `scripts/mobile-ios-pod-refresh.sh` re-invokes this after `pod install`).
 * Salareen mobile builds natively — see .cursor/rules/no-eas-build-mobile.mdc.
 */
const { spawnSync } = require("child_process");
const path = require("path");

const ROOT = path.join(__dirname, "..");

const PATCHES = [
  { script: "patch-expo-localization-ios.js", required: false },
  { script: "patch-expo-device-ios.js", required: true },
  { script: "patch-react-native-runtimescheduler-ios.js", required: false },
  { script: "patch-react-native-jsinspector-ios.js", required: true },
  { script: "patch-react-native-platform-web.js", required: false },
  { script: "patch-ios-expo-configure-project.js", required: false },
  // Xcode 26 noise: hermesc undeclared-global warnings + deprecated allowBluetooth.
  { script: "patch-hermesc-quiet-warnings.js", required: false },
  { script: "patch-allow-bluetooth-hfp-ios.js", required: false },
  // Android: suppress hermesc undeclared-global warnings in Gradle release builds.
  { script: "patch-android-hermesc-quiet.js", required: false },
  // Android: remove deprecated package= from LiveKit manifests (AGP 8+ warning).
  { script: "patch-livekit-manifests.js", required: false },
  // Android: library manifest warnings, and the SoLoader enabled=true override.
  { script: "patch-android-library-warnings.js", required: false },
  // Learner Check: no shutter click per face-check still, faster iOS stills.
  { script: "patch-expo-camera-quiet-capture.js", required: false },
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

  // Metro-only; not required for native compile but harmless to always run.
  runPatch("ensure-metro-local-deps.js");

  if (failedRequired) {
    process.exit(1);
  }
}

main();
