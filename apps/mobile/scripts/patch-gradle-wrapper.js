/**
 * Patch generated Android Gradle files after expo prebuild (or before run:android).
 *
 * Parent ~/node_modules/.pnpm symlinks break Gradle/Node resolution for Expo native
 * builds (duplicate :gradle-plugin, unresolved expo.modules.*). Pin paths to
 * apps/mobile/node_modules and set searchPaths for useExpoModules().
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const wrapperPath = path.join(root, "android", "gradle", "wrapper", "gradle-wrapper.properties");
const settingsPath = path.join(root, "android", "settings.gradle");
const rootBuildPath = path.join(root, "android", "build.gradle");
const appBuildPath = path.join(root, "android", "app", "build.gradle");
const reactNativeSettingsPath = path.join(
  root,
  "node_modules",
  "@react-native",
  "gradle-plugin",
  "settings.gradle.kts",
);

const defaultUrl =
  "https://github.com/gradle/gradle-distributions/releases/download/v8.8.0/gradle-8.8-all.zip";
const distributionUrl = process.env.GRADLE_DISTRIBUTION_URL || defaultUrl;

const localGradlePlugin = "'../node_modules/@react-native/gradle-plugin'";
const patchedMarker = "salareen-local-node-modules";

function writeIfChanged(filePath, content, label) {
  if (!fs.existsSync(filePath)) {
    return false;
  }
  const before = fs.readFileSync(filePath, "utf8");
  if (before === content) {
    return false;
  }
  fs.writeFileSync(filePath, content);
  console.log(label);
  return true;
}

function patchSettingsGradle() {
  if (!fs.existsSync(settingsPath)) {
    return false;
  }
  let content = fs.readFileSync(settingsPath, "utf8");
  if (content.includes(patchedMarker)) {
    return false;
  }

  content = content.replace(
    /includeBuild\(new File\(\["node", "--print", "require\.resolve\('@react-native\/gradle-plugin\/package\.json'\)"\]\.execute\(null, rootDir\)\.text\.trim\(\)\)\.getParentFile\(\)\.toString\(\)\)/,
    `includeBuild(${localGradlePlugin})`,
  );

  content = content.replace(
    /\nincludeBuild\(new File\(\["node", "--print", "require\.resolve\('@react-native\/gradle-plugin\/package\.json', \{ paths: \[require\.resolve\('react-native\/package\.json'\)\] \}\)"\]\.execute\(null, rootDir\)\.text\.trim\(\)\)\.getParentFile\(\)\)\s*/,
    `\nincludeBuild(${localGradlePlugin})\n`,
  );

  content = content.replace(
    /from\(files\(new File\(\["node", "--print", "require\.resolve\('react-native\/package\.json'\)"\]\.execute\(null, rootDir\)\.text\.trim\(\), "\.\.\/gradle\/libs\.versions\.toml"\)\)\)/,
    'from(files(new File(rootDir, "../node_modules/react-native/gradle/libs.versions.toml")))',
  );

  content = content.replace(
    /apply from: new File\(\["node", "--print", "require\.resolve\('expo\/package\.json'\)"\]\.execute\(null, rootDir\)\.text\.trim\(\), "\.\.\/scripts\/autolinking\.gradle"\);/,
    'apply from: new File(rootDir, "../node_modules/expo/scripts/autolinking.gradle");',
  );

  content = content.replace(
    /apply from: new File\(\["node", "--print", "require\.resolve\('@react-native-community\/cli-platform-android\/package\.json', \{ paths: \[require\.resolve\('react-native\/package\.json'\)\] \}\)"\]\.execute\(null, rootDir\)\.text\.trim\(\), "\.\.\/native_modules\.gradle"\);/,
    'apply from: new File(rootDir, "../node_modules/@react-native-community/cli-platform-android/native_modules.gradle");',
  );

  content = content.replace(
    /useExpoModules\(\)/,
    'useExpoModules([ searchPaths: ["../node_modules"] ])',
  );

  if (!content.includes(patchedMarker)) {
    content = `// ${patchedMarker}\n${content}`;
  }

  return writeIfChanged(
    settingsPath,
    content,
    "Android settings.gradle patched: local node_modules paths + useExpoModules searchPaths",
  );
}

function patchRootBuildGradle() {
  if (!fs.existsSync(rootBuildPath)) {
    return false;
  }
  let content = fs.readFileSync(rootBuildPath, "utf8");
  if (content.includes(patchedMarker)) {
    return false;
  }

  content = content.replace(
    /url\(new File\(\['node', '--print', "require\.resolve\('react-native\/package\.json'\)"\]\.execute\(null, rootDir\)\.text\.trim\(\), '\.\.\/android'\)\)/,
    "url(new File(rootDir, '../node_modules/react-native/android'))",
  );

  content = content.replace(
    /url\(new File\(\['node', '--print', "require\.resolve\('jsc-android\/package\.json', \{ paths: \[require\.resolve\('react-native\/package\.json'\)\] \}\)"\]\.execute\(null, rootDir\)\.text\.trim\(\), '\.\.\/dist'\)\)/,
    "url(new File(rootDir, '../node_modules/jsc-android/dist'))",
  );

  if (!content.includes(patchedMarker)) {
    content = content.replace(
      "// Top-level build file",
      `// ${patchedMarker}\n// Top-level build file`,
    );
  }

  return writeIfChanged(
    rootBuildPath,
    content,
    "Android build.gradle patched: local react-native + jsc-android maven paths",
  );
}

/** Ensure :app depends on :expo (api re-exports expo-modules-core for MainApplication.kt). */
function patchAppExpoDependency() {
  if (!fs.existsSync(appBuildPath)) {
    return false;
  }
  let content = fs.readFileSync(appBuildPath, "utf8");
  if (content.includes("implementation project(':expo')")) {
    return false;
  }
  const needle = 'implementation("com.facebook.react:react-android")';
  if (!content.includes(needle)) {
    return false;
  }
  content = content.replace(
    needle,
    `${needle}
    implementation project(':expo')`,
  );
  return writeIfChanged(
    appBuildPath,
    content,
    "Android app/build.gradle patched: implementation project(':expo')",
  );
}

function patchAppBuildGradleLegacyMarker() {
  if (!fs.existsSync(appBuildPath)) {
    return false;
  }
  let content = fs.readFileSync(appBuildPath, "utf8");
  if (content.includes(patchedMarker)) {
    return false;
  }

  content = content.replace(
    /reactNativeDir = new File\(\["node", "--print", "require\.resolve\('react-native\/package\.json'\)"\]\.execute\(null, rootDir\)\.text\.trim\(\)\)\.getParentFile\(\)\.getAbsoluteFile\(\)/,
    'reactNativeDir = new File(projectRoot, "node_modules/react-native").getAbsoluteFile()',
  );

  content = content.replace(
    /hermesCommand = new File\(\["node", "--print", "require\.resolve\('react-native\/package\.json'\)"\]\.execute\(null, rootDir\)\.text\.trim\(\)\)\.getParentFile\(\)\.getAbsolutePath\(\) \+ "\/sdks\/hermesc\/%OS-BIN%\/hermesc"/,
    'hermesCommand = new File(projectRoot, "node_modules/react-native/sdks/hermesc/%OS-BIN%/hermesc").getAbsolutePath()',
  );

  content = content.replace(
    /codegenDir = new File\(\["node", "--print", "require\.resolve\('@react-native\/codegen\/package\.json', \{ paths: \[require\.resolve\('react-native\/package\.json'\)\] \}\)"\]\.execute\(null, rootDir\)\.text\.trim\(\)\)\.getParentFile\(\)\.getAbsoluteFile\(\)/,
    'codegenDir = new File(projectRoot, "node_modules/@react-native/codegen").getAbsoluteFile()',
  );

  content = content.replace(
    /cliFile = new File\(\["node", "--print", "require\.resolve\('@expo\/cli', \{ paths: \[require\.resolve\('expo\/package\.json'\)\] \}\)"\]\.execute\(null, rootDir\)\.text\.trim\(\)\)/,
    'cliFile = new File(projectRoot, "node_modules/@expo/cli/build/bin/cli")',
  );

  content = content.replace(
    /apply from: new File\(\["node", "--print", "require\.resolve\('@react-native-community\/cli-platform-android\/package\.json', \{ paths: \[require\.resolve\('react-native\/package\.json'\)\] \}\)"\]\.execute\(null, rootDir\)\.text\.trim\(\), "\.\.\/native_modules\.gradle"\);/,
    'apply from: new File(rootDir, "../node_modules/@react-native-community/cli-platform-android/native_modules.gradle");',
  );

  content = content.replace(
    'apply plugin: "com.android.application"',
    `// ${patchedMarker}\napply plugin: "com.android.application"`,
  );

  return writeIfChanged(
    appBuildPath,
    content,
    "Android app/build.gradle patched: local react-native + @expo/cli paths",
  );
}

function patchAppBuildGradle() {
  return patchAppBuildGradleLegacyMarker() || patchAppExpoDependency();
}

function patchWrapper() {
  if (!fs.existsSync(wrapperPath)) {
    return false;
  }
  const escapedUrl = distributionUrl.replace("https://", "https\\://");
  const lines = fs.readFileSync(wrapperPath, "utf8").split(/\r?\n/);
  const patched = lines.map((line) =>
    line.startsWith("distributionUrl=") ? `distributionUrl=${escapedUrl}` : line,
  );
  const next = patched.join("\n");
  const before = fs.readFileSync(wrapperPath, "utf8");
  if (before === next) {
    return false;
  }
  fs.writeFileSync(wrapperPath, next);
  console.log(`Gradle wrapper distributionUrl set to ${distributionUrl}`);
  return true;
}

function patchReactNativeGradlePlugin() {
  if (!fs.existsSync(reactNativeSettingsPath)) {
    return false;
  }
  const rnSettings = fs.readFileSync(reactNativeSettingsPath, "utf8");
  const foojayPlugin =
    'plugins { id("org.gradle.toolchains.foojay-resolver-convention").version("0.5.0") }';
  const patchedFoojayPlugin =
    "// Patched by apps/mobile/scripts/patch-gradle-wrapper.js; Java is provided by CI/local env.";
  if (!rnSettings.includes(foojayPlugin)) {
    return false;
  }
  fs.writeFileSync(
    reactNativeSettingsPath,
    rnSettings.replace(foojayPlugin, patchedFoojayPlugin),
  );
  console.log("React Native Foojay toolchain resolver plugin disabled for this build");
  return true;
}

let patchedAny = false;
patchedAny = patchSettingsGradle() || patchedAny;
patchedAny = patchRootBuildGradle() || patchedAny;
patchedAny = patchAppBuildGradle() || patchedAny;
patchedAny = patchWrapper() || patchedAny;
patchedAny = patchReactNativeGradlePlugin() || patchedAny;

if (!patchedAny) {
  if (!fs.existsSync(path.join(root, "android"))) {
    console.error("Android project not found — run: npm run prebuild  (or  npm run native:prebuild:android)");
    process.exit(1);
  }
  console.log("Android Gradle files already patched (no changes needed)");
}
