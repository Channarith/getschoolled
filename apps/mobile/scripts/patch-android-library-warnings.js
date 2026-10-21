/**
 * Silence AGP manifest warnings from libraries we do not author.
 *
 * AGP 8 ignores package= on AndroidManifest.xml and warns when tools:replace
 * names an attribute that no other manifest declares. Namespace stays in each
 * library build.gradle, so removing the ignored attributes does not change
 * the installed app.
 *
 * SoLoader 0.10.5 sets com.facebook.soloader.enabled=false. Expo modules need
 * it true, so that meta-data must keep tools:replace or the release manifest
 * merger fails.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");

const PACKAGE_LIBS = [
  ["node_modules/react-native-svg/android", "com.horcrux.svg"],
  ["node_modules/react-native-safe-area-context/android", "com.th3rdwave.safeareacontext"],
  ["node_modules/@react-native-async-storage/async-storage/android", "com.reactnativecommunity.asyncstorage"],
  ["node_modules/react-native-view-shot/android", "fr.greweb.reactnativeviewshot"],
  ["node_modules/react-native-google-mobile-ads/android", "io.invertase.googlemobileads"],
  ["node_modules/@react-native-ml-kit/face-detection/android", "com.rnmlkit.facedetection"],
];

const REPLACE_ATTRS = [
  [
    "node_modules/expo-file-system/android/src/main/AndroidManifest.xml",
    /\s+tools:replace="android:authorities"/,
  ],
];

const SOLOADER_MANIFEST = "node_modules/expo-modules-core/android/src/main/AndroidManifest.xml";

function ensureNamespace(gradlePath, namespace) {
  if (!fs.existsSync(gradlePath)) return false;
  let src = fs.readFileSync(gradlePath, "utf8");
  if (src.includes(`namespace "${namespace}"`) || src.includes(`namespace '${namespace}'`)) {
    return true;
  }
  if (!src.includes("android {")) return false;
  src = src.replace("android {", `android {\n  namespace "${namespace}"`);
  fs.writeFileSync(gradlePath, src);
  console.log(`patch-android-library-warnings: added namespace ${namespace}`);
  return true;
}

function stripPackage(manifestPath) {
  if (!fs.existsSync(manifestPath)) return;
  const src = fs.readFileSync(manifestPath, "utf8");
  const next = src.replace(/\s+package="[^"]*"/, "");
  if (next === src) return;
  fs.writeFileSync(manifestPath, next);
  console.log(`patch-android-library-warnings: removed package= from ${path.relative(ROOT, manifestPath)}`);
}

function ensureAppSoloaderOverride() {
  const rel = "android/app/src/main/AndroidManifest.xml";
  const filePath = path.join(ROOT, rel);
  if (!fs.existsSync(filePath)) return;
  const src = fs.readFileSync(filePath, "utf8");
  if (src.includes('android:name="com.facebook.soloader.enabled"')) return;
  const entry = '    <meta-data android:name="com.facebook.soloader.enabled" android:value="true" tools:replace="android:value"/>\n';
  const next = src.replace(/<application\b[^>]*>/, (open) => `${open}\n${entry.trimEnd()}`);
  if (next === src) return;
  fs.writeFileSync(filePath, next);
  console.log(`patch-android-library-warnings: SoLoader manifest override kept in ${rel}`);
}

function ensureSoloaderOverride(rel) {
  const filePath = path.join(ROOT, rel);
  if (!fs.existsSync(filePath)) return;
  const src = fs.readFileSync(filePath, "utf8");
  if (!src.includes('android:name="com.facebook.soloader.enabled"')) return;
  if (/com\.facebook\.soloader\.enabled"[\s\S]{0,180}tools:replace="android:value"/.test(src)) return;
  const next = src.replace(
    /(android:name="com\.facebook\.soloader\.enabled"[\s\S]*?android:value="true")/,
    '$1 tools:replace="android:value"',
  );
  if (next === src) return;
  fs.writeFileSync(filePath, next);
  console.log(`patch-android-library-warnings: SoLoader manifest override kept in ${rel}`);
}

function main() {
  for (const [dir, namespace] of PACKAGE_LIBS) {
    const base = path.join(ROOT, dir);
    if (!ensureNamespace(path.join(base, "build.gradle"), namespace)) {
      console.log(`patch-android-library-warnings: skip ${dir} (no build.gradle namespace)`);
      continue;
    }
    stripPackage(path.join(base, "src", "main", "AndroidManifest.xml"));
  }

  for (const [rel, pattern] of REPLACE_ATTRS) {
    const filePath = path.join(ROOT, rel);
    if (!fs.existsSync(filePath)) continue;
    const src = fs.readFileSync(filePath, "utf8");
    const next = src.replace(pattern, "");
    if (next === src) continue;
    fs.writeFileSync(filePath, next);
    console.log(`patch-android-library-warnings: removed unused tools:replace from ${rel}`);
  }
  ensureSoloaderOverride(SOLOADER_MANIFEST);
  ensureAppSoloaderOverride();
}

main();
