#!/usr/bin/env node
/**
 * Download Expo Go from Expo servers and install on simulator/emulator.
 * Uses native fetch (Node 18+) — @expo/cli's node-fetch path fails on Node 22
 * with ERR_STREAM_PREMATURE_CLOSE against exp.host.
 *
 * Usage:
 *   node scripts/mobile-install-expo-go-direct.js ios
 *   node scripts/mobile-install-expo-go-direct.js android
 */
'use strict';

const { execSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { pipeline } = require('stream/promises');
const { createWriteStream } = require('fs');

const ROOT = path.join(__dirname, '..');
const PLATFORM = (process.argv[2] || 'ios').toLowerCase();
const EXPO_HOME = process.env.EXPO_HOME || path.join(process.env.HOME || '', '.expo');
const VERSIONS_URL = 'https://exp.host/--/api/v2/versions/latest';

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

function getExpoSdkVersion() {
  try {
    const { getExpoSDKVersion } = require('@expo/config/build/getExpoSDKVersion');
    return getExpoSDKVersion(ROOT);
  } catch (err) {
    fail(`Could not read Expo SDK version (${err.message})`);
  }
}

async function fetchJson(url) {
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} from ${url}`);
  }
  return res.json();
}

async function downloadFile(url, outputPath) {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} downloading ${url}`);
  }
  if (!res.body) {
    throw new Error(`No response body from ${url}`);
  }
  await pipeline(res.body, createWriteStream(outputPath));
}

async function resolveExpoGoUrl(sdkVersion, platform) {
  const payload = await fetchJson(VERSIONS_URL);
  const versions = payload?.data?.sdkVersions;
  if (!versions || !versions[sdkVersion]) {
    throw new Error(`No Expo Go build listed for SDK ${sdkVersion}`);
  }
  const entry = versions[sdkVersion];
  const url = platform === 'ios' ? entry.iosClientUrl : entry.androidClientUrl;
  if (!url) {
    throw new Error(`No Expo Go ${platform} URL for SDK ${sdkVersion}`);
  }
  return url;
}

function archiveBaseName(url) {
  return path.basename(url).replace(/\.(tar\.gz|tgz|apk)$/i, '');
}

async function downloadIosExpoGo(url) {
  const base = archiveBaseName(url);
  const appDir = path.join(EXPO_HOME, 'ios-simulator-app-cache', `${base}.app`);
  if (fs.existsSync(appDir) && fs.readdirSync(appDir).length > 0) {
    console.log(`    Using cached app: ${appDir}`);
    return appDir;
  }
  const archivePath = path.join(EXPO_HOME, 'ios-simulator-app-cache', `${base}.tar.gz`);
  console.log(`    Downloading ${url}`);
  await downloadFile(url, archivePath);
  fs.mkdirSync(appDir, { recursive: true });
  console.log(`    Extracting to ${appDir}`);
  run(`tar -xzf "${archivePath}" -C "${appDir}"`);
  return appDir;
}

async function downloadAndroidExpoGo(url) {
  const base = archiveBaseName(url);
  const apkPath = path.join(EXPO_HOME, 'android-apk-cache', `${base}.apk`);
  if (fs.existsSync(apkPath)) {
    console.log(`    Using cached apk: ${apkPath}`);
    return apkPath;
  }
  console.log(`    Downloading ${url}`);
  await downloadFile(url, apkPath);
  return apkPath;
}

async function main() {
  if (!['ios', 'android'].includes(PLATFORM)) {
    fail(`platform must be ios or android, got: ${PLATFORM}`);
  }

  const sdkVersion = getExpoSdkVersion();
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

  const url = await resolveExpoGoUrl(sdkVersion, PLATFORM);
  const binaryPath =
    PLATFORM === 'ios'
      ? await downloadIosExpoGo(url)
      : await downloadAndroidExpoGo(url);
  console.log(`    Ready: ${binaryPath}`);

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

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(err?.message || err);
    console.error('');
    console.error('If download failed (VPN/firewall), try:');
    console.error('  https://expo.dev/go?platform=ios&sdkVersion=51');
    console.error('  Or: bash scripts/mobile-install-expo-go-ios.sh --metro-fallback');
    process.exit(1);
  });
