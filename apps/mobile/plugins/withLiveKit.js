// `@expo/config-plugins` is a transitive dep of `expo` and pinned directly in
// package.json so it resolves from apps/mobile/node_modules on EAS. Fall back to
// a no-op if it is somehow unresolvable so `expo config` never hard-fails.
//
// NOTE: `@expo/config-plugins` v8 (Expo SDK 51) does NOT export a top-level
// `withPermissions`; Android permissions go through
// `AndroidConfig.Permissions.withPermissions(config, string[])`. iOS usage
// strings + background modes are set via `withInfoPlist`.
let AndroidConfig;
let withAppBuildGradle;
let withInfoPlist;
let withMainApplication;
try {
  ({ AndroidConfig, withAppBuildGradle, withInfoPlist, withMainApplication } = require("@expo/config-plugins"));
} catch (err) {
  console.warn(
    "[withLiveKit] @expo/config-plugins unavailable; skipping plugin:",
    err && err.message ? err.message : err,
  );
  module.exports = (config) => config;
  return;
}

const IOS_CAMERA_MSG =
  "Salareen uses your camera for live class video when you hold the speaking floor.";
const IOS_MIC_MSG =
  "Salareen uses your microphone for live class audio when you hold the speaking floor.";

const ANDROID_PERMISSIONS = [
  "android.permission.CAMERA",
  "android.permission.RECORD_AUDIO",
  "android.permission.MODIFY_AUDIO_SETTINGS",
];

function withLiveKit(config) {
  // Android permissions (AndroidManifest.xml).
  if (AndroidConfig && AndroidConfig.Permissions && AndroidConfig.Permissions.withPermissions) {
    config = AndroidConfig.Permissions.withPermissions(config, ANDROID_PERMISSIONS);
  }

  // Android: avoid duplicate libc++_shared.so when linking the WebRTC .so.
  config = withAppBuildGradle(config, (cfg) => {
    if (cfg.modResults.language !== "groovy") return cfg;
    const src = cfg.modResults.contents;
    if (!src.includes("packagingOptions")) {
      cfg.modResults.contents = src.replace(
        /android\s*\{/,
        `android {
    packagingOptions {
        pickFirst 'lib/**/libc++_shared.so'
    }`,
      );
    }
    return cfg;
  });

  // Android: patch MainApplication.kt to call LiveKitReactNative.setup(this)
  // in onCreate(). LiveKit throws "Audio device module is not initialized!"
  // at runtime if this call is missing — the audio session cannot be configured
  // and the app crashes when joining any live room.
  if (withMainApplication) {
    const LK_IMPORT = "import com.livekit.reactnative.LiveKitReactNative";
    const LK_SETUP  = "    LiveKitReactNative.setup(this)";
    config = withMainApplication(config, (cfg) => {
      let src = cfg.modResults.contents;
      // Add import below the last expo import (idempotent).
      if (!src.includes(LK_IMPORT)) {
        src = src.replace(
          /(import expo\.modules\.ReactNativeHostWrapper)/,
          `$1\n\n${LK_IMPORT}`,
        );
      }
      // Add setup call immediately after super.onCreate() (idempotent).
      if (!src.includes("LiveKitReactNative.setup")) {
        src = src.replace(
          /super\.onCreate\(\)/,
          `super.onCreate()\n${LK_SETUP}`,
        );
      }
      cfg.modResults.contents = src;
      return cfg;
    });
  }

  // iOS: camera/mic usage strings + background audio for live rooms.
  return withInfoPlist(config, (cfg) => {
    if (!cfg.modResults.NSCameraUsageDescription) {
      cfg.modResults.NSCameraUsageDescription = IOS_CAMERA_MSG;
    }
    if (!cfg.modResults.NSMicrophoneUsageDescription) {
      cfg.modResults.NSMicrophoneUsageDescription = IOS_MIC_MSG;
    }
    cfg.modResults.UIBackgroundModes = [
      ...new Set([...(cfg.modResults.UIBackgroundModes || []), "audio"]),
    ];
    return cfg;
  });
}

module.exports = withLiveKit;
