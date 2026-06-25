/**
 * Dynamic Expo config (merges static app.json via the config param).
 *
 * MOBILE_DEPLOY_MODE=local|cloud  (default cloud — same HTTPS origin as www.salareen.com)
 * MOBILE_CLOUD_BASE_URL=https://www.salareen.com
 */
const CLOUD_DEFAULT = "https://www.salareen.com";

module.exports = ({ config }) => {
  const extra = config.extra || {};
  const cloudBaseUrl = (
    process.env.MOBILE_CLOUD_BASE_URL
    || extra.cloudBaseUrl
    || CLOUD_DEFAULT
  ).replace(/\/$/, "");
  const deployMode = process.env.MOBILE_DEPLOY_MODE || extra.deployMode || "cloud";

  const plugins = [...(config.plugins || [])];
  const hasBuildProps = plugins.some(
    (entry) => (Array.isArray(entry) ? entry[0] : entry) === "expo-build-properties",
  );
  if (!hasBuildProps) {
    plugins.push([
      "expo-build-properties",
      {
        android: {
          // Local Vultr HTTP + Android emulator dev client (not valid in app.json schema).
          usesCleartextTraffic: true,
        },
      },
    ]);
  }

  return {
    ...config,
    plugins,
    extra: {
      ...extra,
      deployMode,
      cloudBaseUrl,
    },
  };
};
