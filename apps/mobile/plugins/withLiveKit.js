const {
  withAppBuildGradle,
  withInfoPlist,
  withPermissions,
} = require("@expo/config-plugins");

function withLiveKit(config) {
  config = withPermissions(config, {
    ios: {
      NSCameraUsageDescription:
        "Salareen uses your camera for live class video when you hold the speaking floor.",
      NSMicrophoneUsageDescription:
        "Salareen uses your microphone for live class audio when you hold the speaking floor.",
    },
    android: [
      "android.permission.CAMERA",
      "android.permission.RECORD_AUDIO",
      "android.permission.MODIFY_AUDIO_SETTINGS",
    ],
  });

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

  return withInfoPlist(config, (cfg) => {
    cfg.modResults.UIBackgroundModes = [
      ...(cfg.modResults.UIBackgroundModes || []),
      "audio",
    ];
    return cfg;
  });
}

module.exports = withLiveKit;
