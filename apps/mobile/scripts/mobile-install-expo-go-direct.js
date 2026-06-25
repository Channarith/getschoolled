#!/usr/bin/env node
/**
 * Download Expo Go from Expo servers and install on simulator/emulator.
 * Uses @expo/cli internals (same as `expo start --ios`) without starting Metro.
 *
 * Usage:
 *   node scripts/mobile-install-expo-go-direct.js ios
 *   node scripts/mobile-install-expo-go-direct.js android
 */
'use strict';

const { execSync, spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const PLATFORM = (process.argv[2] || 'ios').toLowerCase();

function run(cmd, opts = {}) {
  return execSync(cmd, { stdio: 'inherit', ...opts });
}

function runCapture(cmd) {
  return execSync(cmd, { encoding: 'utf8' }).trim();
}

function fail(msg) {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

async function main() {
  if (!['ios', 'android'].includes(PLATFORM)) {
    fail(`platform must be ios or android, got: ${PLATFORM}`);
  }

  let getExpoSDKVersion;
  let downloadExpoGoAsync;
  try {
    ({ getExpoSDKVersion } = require('@expo/config/build/getExpoSDKVersion'));
    ({ downloadExpoGoAsync } = require('@expo/cli/build/src/utils/downloadExpoGoAsync'));
  } catch (err) {
    fail(
      `Expo CLI modules missing (${err.message}). Run: bash scripts/mobile-install.sh`
    );
  }

  const sdkVersion = getExpoSDKVersion(ROOT);
  console.log(`==> Expo Go direct install (${PLATFORM}, SDK ${sdkVersion})`);
  console.log('    Needs network once — downloads from Expo CDN (not Metro)');

  if (PLATFORM === 'ios') {
    if (process.platform !== 'darwin') {
      fail('iOS simulator install requires macOS');
    }
    try {
      run('xcode-select -p');
    } catch {
      fail('Xcode CLI not found — install Xcode from the App Store');
    }
    try {
      const booted = runCapture('xcrun simctl list devices booted');
      if (!booted.includes('Booted')) {
        throw new Error('no booted sim');
      }
    } catch {
      console.log('    No booted simulator — booting default iPhone 16…');
      const simUtils = path.join(__dirname, 'mobile-sim-utils.sh');
      run(`bash -c '. "${simUtils}" && mobile_ios_boot_simulator'`);
    }
  } else {
    const androidHome =
      process.env.ANDROID_HOME ||
      process.env.ANDROID_SDK_ROOT ||
      `${process.env.HOME}/Library/Android/sdk`;
    const adb = path.join(androidHome, 'platform-tools', 'adb');
    try {
      const out = runCapture(`"${adb}" devices`);
      if (!out.includes('emulator')) {
        fail('Boot an Android emulator first (Android Studio → Device Manager → Play)');
      }
    } catch {
      fail(`adb not found at ${adb} — set ANDROID_HOME`);
    }
  }

  const binaryPath = await downloadExpoGoAsync(PLATFORM, { sdkVersion });
  console.log(`    Downloaded: ${binaryPath}`);

  if (PLATFORM === 'ios') {
    run(`xcrun simctl install booted "${binaryPath}"`);
    console.log('OK Expo Go installed on iOS Simulator (host.exp.Exponent)');
  } else {
    const androidHome =
      process.env.ANDROID_HOME ||
      process.env.ANDROID_SDK_ROOT ||
      `${process.env.HOME}/Library/Android/sdk`;
    const adb = path.join(androidHome, 'platform-tools', 'adb');
    const result = spawnSync(adb, ['install', '-r', binaryPath], { stdio: 'inherit' });
    if (result.status !== 0) {
      fail('adb install failed');
    }
    console.log('OK Expo Go installed on Android emulator (host.exp.exponent)');
  }
}

main().catch((err) => {
  console.error(err?.message || err);
  console.error('');
  console.error('If download failed (VPN/firewall), try:');
  console.error('  https://expo.dev/go?platform=ios&sdkVersion=51');
  console.error('  Or: bash scripts/mobile-install-expo-go-ios.sh --metro-fallback');
  process.exit(1);
});
