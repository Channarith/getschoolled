/**
 * Expo config: app.json defaults + env overrides for backend target.
 *
 * MOBILE_DEPLOY_MODE=local|cloud  (default cloud — Vultr VKE at MOBILE_CLOUD_BASE_URL)
 * MOBILE_CLOUD_BASE_URL=http://45.63.91.80
 */
const appJson = require("./app.json");

module.exports = () => {
  const base = appJson.expo;
  const extra = base.extra || {};
  const cloudBaseUrl = (
    process.env.MOBILE_CLOUD_BASE_URL
    || extra.cloudBaseUrl
    || "http://45.63.91.80"
  ).replace(/\/$/, "");
  const deployMode = process.env.MOBILE_DEPLOY_MODE || extra.deployMode || "cloud";

  return {
    expo: {
      ...base,
      extra: {
        ...extra,
        deployMode,
        cloudBaseUrl,
      },
    },
  };
};
