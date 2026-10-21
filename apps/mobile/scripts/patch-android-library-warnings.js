/**
 * Silence AGP manifest warnings from libraries we do not author.
 *
 * AGP 8 ignores package= on AndroidManifest.xml and warns when tools:replace
 * names an attribute that no other manifest declares. Namespace stays in each
 * library build.gradle, so removing the ignored attributes does not change
 * the installed app.
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
];

const REPLACE_ATTRS = [
  [
    "node_modules/expo-file-system/android/src/main/AndroidManifest.xml",
    /\s+tools:replace="android:authorities"/,
  ],
  [
    "node_modules/expo-modules-core/android/src/main/AndroidManifest.xml",
    /\s+tools:replace="android:value"/,
  ],
];

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
}

main();
