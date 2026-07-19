/**
 * Remove deprecated `package=` attribute from LiveKit Android manifests.
 *
 * @livekit/react-native and @livekit/react-native-webrtc still declare
 * `package="com.livekit.reactnative"` and `package="com.oney.WebRTCModule"`
 * in their AndroidManifest.xml files. AGP 8+ moved the namespace declaration
 * to build.gradle and no longer reads it from the manifest — it warns:
 *
 *   "Setting the namespace via the package attribute in the source
 *    AndroidManifest.xml is no longer supported, and the value is ignored."
 *
 * These warnings will become errors in a future AGP version. Since the value
 * is already declared in each module's build.gradle, removing it from the
 * manifest is the correct migration and has no functional impact.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");

const MANIFESTS = [
  {
    file: "node_modules/@livekit/react-native/android/src/main/AndroidManifest.xml",
    attr: /\s+package="com\.livekit\.reactnative"/g,
    label: "@livekit/react-native",
  },
  {
    file: "node_modules/@livekit/react-native-webrtc/android/src/main/AndroidManifest.xml",
    attr: /\s+package="com\.oney\.WebRTCModule"/g,
    label: "@livekit/react-native-webrtc",
  },
];

function main() {
  for (const { file, attr, label } of MANIFESTS) {
    const filePath = path.join(ROOT, file);
    if (!fs.existsSync(filePath)) {
      console.log(`patch-livekit-manifests: ${label} manifest missing — skip`);
      continue;
    }

    let src = fs.readFileSync(filePath, "utf8");
    if (!attr.test(src)) {
      // Reset lastIndex (global regex)
      attr.lastIndex = 0;
      console.log(`patch-livekit-manifests: ${label} already patched or attr not found`);
      continue;
    }

    attr.lastIndex = 0;
    src = src.replace(attr, "");
    fs.writeFileSync(filePath, src);
    console.log(`patch-livekit-manifests: removed deprecated package= from ${label}`);
  }
}

main();
