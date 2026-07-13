#!/usr/bin/env node
/**
 * Fail fast when local Expo config plugins are broken.
 *
 * EAS runs `expo config` BEFORE prebuild (to compute the EAS Update runtime
 * version). Two recurring failure modes:
 *   1. A local plugin `require()`s a package that isn't a DIRECT dep
 *      (MODULE_NOT_FOUND on `@expo/config-plugins`).
 *   2. A plugin loads but calls a non-existent API when invoked
 *      (e.g. `withPermissions is not a function` — not a top-level export in v8).
 *
 * This script reproduces the exact `expo config` invocation so both are caught
 * during the install hook instead of mid-build.
 */
const { execFileSync } = require("child_process");
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

if (fs.existsSync(pluginsDir)) {
  for (const name of fs.readdirSync(pluginsDir)) {
    if (!name.endsWith(".js")) continue;
    try {
      const plugin = require(path.join(pluginsDir, name));
      if (typeof plugin !== "function") {
        fail(`${name} must export a function(config) => config`);
      }
    } catch (err) {
      fail(`${name} failed to load: ${err && err.message ? err.message : err}`);
    }
  }
}

// Definitive smoke test: run the same command EAS uses for runtime version.
const expoCli = path.join(ROOT, "node_modules", "expo", "bin", "cli");
if (fs.existsSync(expoCli)) {
  try {
    execFileSync("node", [expoCli, "config", "--json", "--full", "--type", "public"], {
      cwd: ROOT,
      stdio: ["ignore", "ignore", "pipe"],
      env: { ...process.env, EXPO_NO_TELEMETRY: "1" },
    });
  } catch (err) {
    const stderr = err && err.stderr ? err.stderr.toString() : "";
    fail(
      "`expo config` failed — a config plugin is broken (this is what EAS hits "
        + `before prebuild):\n${stderr.trim() || (err && err.message) || err}`,
    );
  }
} else {
  console.warn("WARN verify-expo-config-plugins: expo cli not found, skipped `expo config` smoke test");
}

console.log("OK verify-expo-config-plugins");
