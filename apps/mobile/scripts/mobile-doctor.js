#!/usr/bin/env node
/**
 * Quick environment check before running the Expo app on macOS (or Linux CI).
 * Run from apps/mobile:  pnpm run doctor
 */
const { execSync, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const isDarwin = process.platform === "darwin";
const verbose = process.argv.includes("--verbose") || process.argv.includes("-v");
let failures = 0;
let warnings = 0;

function ok(msg) {
  console.log(`  OK   ${msg}`);
}
function warn(msg) {
  warnings += 1;
  console.log(`  WARN ${msg}`);
}
function fail(msg) {
  failures += 1;
  console.log(`  FAIL ${msg}`);
}
function run(cmd) {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
  } catch {
    return null;
  }
}

console.log("Salareen mobile — environment doctor\n");
console.log(`Platform: ${process.platform} ${process.arch}`);
console.log(`CWD:      ${process.cwd()}`);
if (!process.cwd().endsWith(`${path.sep}apps${path.sep}mobile`) &&
    !fs.existsSync(path.join(process.cwd(), "app.json"))) {
  fail('Run this from apps/mobile (cd apps/mobile && pnpm run doctor)');
}

const nodeMajor = Number(process.version.slice(1).split(".")[0]);
if (nodeMajor >= 18) ok(`Node ${process.version}`);
else fail(`Node ${process.version} — need Node 18+`);

if (fs.existsSync(path.join(ROOT, "node_modules", ".bin", "expo"))) {
  const ver = run(`node "${path.join(ROOT, "node_modules", ".bin", "expo")}" --version`);
  ok(`Expo CLI ${ver || "present"}`);
} else {
  fail("node_modules missing — run: pnpm install");
}

if (fs.existsSync(path.join(ROOT, "node_modules", "babel-preset-expo"))) {
  ok("babel-preset-expo installed");
} else {
  warn("babel-preset-expo missing — run: pnpm install");
}

if (fs.existsSync(path.join(ROOT, "app.json"))) ok("app.json found");
else fail("app.json not found");

if (isDarwin) {
  console.log("\nmacOS / iOS Simulator checks:");
  const xcode = run("xcode-select -p");
  if (xcode) ok(`Xcode CLI: ${xcode}`);
  else fail("Xcode Command Line Tools not found — install Xcode from the App Store");

  const sims = run("xcrun simctl list devices available 2>/dev/null | grep -E 'iPhone|iPad' | head -3");
  if (sims) ok(`Simulators available:\n       ${sims.replace(/\n/g, "\n       ")}`);
  else warn("No iOS simulators listed — open Xcode -> Settings -> Platforms");

  const xcodebuild = run("xcodebuild -version 2>/dev/null | head -1");
  if (xcodebuild) ok(xcodebuild);
  else warn("xcodebuild not working — open Xcode once and accept the license");
}

console.log("\nAndroid emulator checks (optional):");
const androidHome = process.env.ANDROID_HOME || process.env.ANDROID_SDK_ROOT;
if (androidHome && fs.existsSync(androidHome)) {
  ok(`ANDROID_HOME=${androidHome}`);
  const avds = run(`${path.join(androidHome, "emulator", "emulator")} -list-avds 2>/dev/null`);
  if (avds) ok(`AVDs: ${avds.replace(/\n/g, ", ")}`);
  else warn("No Android AVDs — create one in Android Studio Device Manager");
} else if (isDarwin) {
  warn("ANDROID_HOME unset — needed only for Android emulator (add to ~/.zshrc)");
}

console.log("\nRecommended launch commands (from apps/mobile):");
console.log("  pnpm run launch:ios              # doctor + open Simulator + Expo Go");
console.log("  pnpm run launch:ios:debug        # same with EXPO_DEBUG=1");
console.log("  pnpm run launch:android          # boot AVD if needed + Expo Go");
console.log("  pnpm run launch:android:debug    # verbose Android launch");
console.log("  pnpm run dev:ios                 # Expo Go (manual Simulator open)");
console.log("  pnpm run dev:ios:debug           # EXPO_DEBUG=1 + DEBUG=expo:*");
console.log("  pnpm ios                         # native compile (slow; first run 10–20 min)");
console.log("  pnpm run launch:ios:native:debug # native + verbose");
console.log("\nIf nothing happens when you run pnpm:");
console.log("  1. Confirm you are in apps/mobile (not the repo root).");
console.log("  2. Use launch:ios / dev:ios — NOT plain pnpm ios on first try.");
console.log("  3. macOS: open Simulator first:  open -a Simulator");
console.log("  4. Verbose logs:  pnpm run dev:ios:debug");
console.log("  5. Full launcher: pnpm run launch:ios:debug");
console.log("  6. Offline mode:  pnpm run dev:ios:offline");

if (verbose) {
  console.log("\nVerbose diagnostics:");
  const pnpmVer = run("pnpm --version");
  if (pnpmVer) ok(`pnpm ${pnpmVer}`);
  else warn("pnpm not on PATH — install: npm i -g pnpm");

  const whichExpo = run(`node "${path.join(ROOT, "node_modules", ".bin", "expo")}" --version`);
  if (whichExpo) ok(`expo binary: ${whichExpo}`);

  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
    ok(`package: ${pkg.name}@${pkg.version}`);
  } catch {
    warn("Could not read package.json");
  }

  if (isDarwin) {
    const simBoot = run("xcrun simctl list devices booted 2>/dev/null | grep -v '== Devices ==' | head -5");
    if (simBoot) ok(`Booted simulators:\n       ${simBoot.replace(/\n/g, "\n       ")}`);
    else console.log("  (no booted iOS simulators)");
  }

  const adb = androidHome ? path.join(androidHome, "platform-tools", "adb") : null;
  if (adb && fs.existsSync(adb)) {
    const devices = run(`"${adb}" devices 2>/dev/null`);
    if (devices) ok(`adb devices:\n       ${devices.replace(/\n/g, "\n       ")}`);
  }
}

console.log("");
if (failures) {
  console.log(`Result: ${failures} failure(s), ${warnings} warning(s) — fix FAIL items first.`);
  process.exit(1);
}
console.log(`Result: ready (${warnings} warning(s)). Try: pnpm run dev:ios`);
process.exit(0);
