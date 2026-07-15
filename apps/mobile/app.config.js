/**
 * Dynamic Expo config (merges static app.json via the config param).
 *
 * MOBILE_DEPLOY_MODE=local|cloud  (default cloud — same HTTPS origin as www.salareen.com)
 * MOBILE_CLOUD_BASE_URL=https://www.salareen.com
 */
const CLOUD_DEFAULT = "https://www.salareen.com";
const CLOUD_FAILOVER_DEFAULT = "http://45.63.91.80";

module.exports = ({ config }) => {
  const extra = config.extra || {};
  const cloudBaseUrl = (
    process.env.MOBILE_CLOUD_BASE_URL
    || extra.cloudBaseUrl
    || CLOUD_DEFAULT
  ).replace(/\/$/, "");
  const cloudFailoverBaseUrl = (
    process.env.MOBILE_CLOUD_FAILOVER_BASE_URL
    || extra.cloudFailoverBaseUrl
    || CLOUD_FAILOVER_DEFAULT
  ).replace(/\/$/, "");
  const deployMode = process.env.MOBILE_DEPLOY_MODE || extra.deployMode || "cloud";

  // QA quick-fill accounts are a dev/preview convenience. They are injected into
  // `extra` (and thus config.ts / the login screen) for every profile EXCEPT
  // production, so admin/QA credentials never ship in a release bundle
  // (B-SEC-1 / risk R5). EAS sets EAS_BUILD_PROFILE during cloud builds; a bare
  // `expo start` / dev build has no profile and gets the accounts.
  const isProductionBuild = process.env.EAS_BUILD_PROFILE === "production";
  const qaTestAccounts = isProductionBuild
    ? []
    : [
        { label: "QA Pro", email: "qa-pro@salareen.com", password: "QaTest123" },
        { label: "QA3", email: "qa3", password: "QaTest123" },
        { label: "Admin", email: "admin@salareen.com", password: "88888888" },
      ];

  const plugins = [...(config.plugins || [])];
  const hasBuildProps = plugins.some(
    (entry) => (Array.isArray(entry) ? entry[0] : entry) === "expo-build-properties",
  );
  if (!hasBuildProps) {
    plugins.push([
      "expo-build-properties",
      {
        ios: {
          deploymentTarget: "13.4",
        },
        android: {
          // LiveKit (@livekit/react-native m137) requires Android minSdk 24;
          // Expo SDK 51 default is 23 -> manifest merger fails without this.
          minSdkVersion: 24,
          // Local Vultr HTTP + Android emulator dev client (not valid in app.json schema).
          usesCleartextTraffic: true,
        },
      },
    ]);
  }
  const hasExpoConfigureFix = plugins.some(
    (entry) =>
      (Array.isArray(entry) ? entry[0] : entry) === "./plugins/withIosExpoConfigureFix.js",
  );
  if (!hasExpoConfigureFix) {
    plugins.push("./plugins/withIosExpoConfigureFix.js");
  }
  if (!plugins.some((entry) => (Array.isArray(entry) ? entry[0] : entry) === "./plugins/withLiveKit.js")) {
    plugins.push("./plugins/withLiveKit.js");
  }
  const admobAndroidAppId =
    process.env.ADMOB_ANDROID_APP_ID || "ca-app-pub-3940256099942544~3347511713";
  const admobIosAppId =
    process.env.ADMOB_IOS_APP_ID || "ca-app-pub-3940256099942544~1458002511";
  // Only register the AdMob config plugin when the module is actually installed.
  // Otherwise prebuild hard-fails with "Failed to resolve plugin for module
  // react-native-google-mobile-ads" on a machine whose node_modules is stale/
  // incomplete. It's a declared dependency — the real fix is `pnpm install` — but
  // we degrade gracefully (ads no-op at runtime via guarded require) instead of
  // crashing the whole build.
  let adsPluginInstalled = false;
  try {
    require.resolve("react-native-google-mobile-ads/app.plugin.js");
    adsPluginInstalled = true;
  } catch {
    try {
      require.resolve("react-native-google-mobile-ads");
      adsPluginInstalled = true;
    } catch {
      adsPluginInstalled = false;
    }
  }
  const adsAlreadyRegistered = plugins.some(
    (entry) => (Array.isArray(entry) ? entry[0] : entry) === "react-native-google-mobile-ads",
  );
  if (adsPluginInstalled && !adsAlreadyRegistered) {
    plugins.push([
      "react-native-google-mobile-ads",
      { androidAppId: admobAndroidAppId, iosAppId: admobIosAppId },
    ]);
  } else if (!adsPluginInstalled) {
    console.warn(
      "[app.config] react-native-google-mobile-ads is not installed — skipping the " +
      "AdMob config plugin (ads will be disabled). Run `pnpm install` in apps/mobile to enable it.",
    );
  }

  return {
    ...config,
    plugins,
    extra: {
      ...extra,
      deployMode,
      cloudBaseUrl,
      cloudFailoverBaseUrl,
      qaTestAccounts,
      admobBannerAndroid:
        process.env.ADMOB_BANNER_ANDROID || "ca-app-pub-3940256099942544/6300978111",
      admobBannerIos:
        process.env.ADMOB_BANNER_IOS || "ca-app-pub-3940256099942544/2934735716",
      admobInterstitialAndroid:
        process.env.ADMOB_INTERSTITIAL_ANDROID || "ca-app-pub-3940256099942544/1033173712",
      admobInterstitialIos:
        process.env.ADMOB_INTERSTITIAL_IOS || "ca-app-pub-3940256099942544/4411468910",
    },
  };
};
