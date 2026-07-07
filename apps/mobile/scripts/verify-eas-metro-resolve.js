#!/usr/bin/env node
/**
 * Fail EAS early if Metro/export:embed cannot resolve critical modules under pnpm.
 * Run from eas-build-post-install.sh after materialize + patch steps.
 */
const path = require("path");

const root = path.join(__dirname, "..");

/** @type {{ label: string; spec: string }[]} */
const REQUIRED = [
  { label: "@babel/runtime", spec: "@babel/runtime/package.json" },
  { label: "expo-asset", spec: "expo-asset/package.json" },
  { label: "@react-native/assets-registry", spec: "@react-native/assets-registry/registry.js" },
  { label: "react-native", spec: "react-native/package.json" },
  { label: "expo", spec: "expo/package.json" },
];

function main() {
  const missing = [];
  for (const { label, spec } of REQUIRED) {
    try {
      const resolved = require.resolve(spec, { paths: [root] });
      console.log(`OK resolve ${label} -> ${resolved}`);
    } catch (err) {
      missing.push({ label, spec, err: err.message });
    }
  }

  if (missing.length === 0) {
    console.log("OK eas metro resolve checks");
    return;
  }

  console.error("ERROR: EAS Metro cannot resolve required modules:");
  for (const m of missing) {
    console.error(`  - ${m.label} (${m.spec}): ${m.err}`);
  }
  console.error("");
  console.error("  Fix: add missing packages as direct dependencies in apps/mobile/package.json");
  console.error("  and ensure eas.json installCommand uses hoisted pnpm (node-linker=hoisted).");
  process.exit(1);
}

main();
