#!/usr/bin/env node
/**
 * Fail fast when local Expo config plugins cannot resolve @expo/config-plugins.
 * EAS runs `expo config` before prebuild; missing direct dep causes MODULE_NOT_FOUND.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const pluginsDir = path.join(ROOT, "plugins");

function fail(msg) {
  console.error(`ERROR: verify-expo-config-plugins: ${msg}`);
  process.exit(1);
}

try {
  require.resolve("@expo/config-plugins", { paths: [ROOT] });
} catch {
  fail(
    "@expo/config-plugins not resolvable from apps/mobile — add it as a direct "
      + "dependency in package.json (pin to the version bundled with your Expo SDK).",
  );
}

if (!fs.existsSync(pluginsDir)) {
  console.log("OK verify-expo-config-plugins (no plugins dir)");
  process.exit(0);
}

for (const name of fs.readdirSync(pluginsDir)) {
  if (!name.endsWith(".js")) continue;
  const pluginPath = path.join(pluginsDir, name);
  try {
    const plugin = require(pluginPath);
    if (typeof plugin !== "function") {
      fail(`${name} must export a function(config) => config`);
    }
  } catch (err) {
    fail(`${name} failed to load: ${err && err.message ? err.message : err}`);
  }
}

console.log("OK verify-expo-config-plugins");
