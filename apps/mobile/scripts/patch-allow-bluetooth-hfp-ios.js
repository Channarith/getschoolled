/**
 * Xcode 26 / iOS SDK: AVAudioSession.CategoryOptions.allowBluetooth was renamed
 * to allowBluetoothHFP. Patch only session-option *usages* — never rename
 * expo-speech-recognition's JS enum `CategoryOptionsParam.allowBluetooth`
 * (that broke Archive: "type has no member 'allowBluetoothHFP'").
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");

const TARGETS = [
  "node_modules/@livekit/react-native/ios/LiveKitReactNativeModule.swift",
  "node_modules/expo-speech-recognition/ios/ExpoSpeechRecognizer.swift",
  "node_modules/expo-speech-recognition/ios/SpeechRecognitionOptions.swift",
  "node_modules/expo-speech-recognition/ios/ExpoSpeechRecognitionModule.swift",
];

function resolvePaths() {
  const out = [];
  for (const rel of TARGETS) {
    const abs = path.join(ROOT, rel);
    if (fs.existsSync(abs)) {
      out.push(abs);
      continue;
    }
    try {
      if (rel.includes("@livekit/react-native/")) {
        const pkg = path.dirname(
          require.resolve("@livekit/react-native/package.json", { paths: [ROOT] }),
        );
        const p = path.join(pkg, "ios", "LiveKitReactNativeModule.swift");
        if (fs.existsSync(p)) out.push(p);
      } else if (rel.includes("expo-speech-recognition/")) {
        const pkg = path.dirname(
          require.resolve("expo-speech-recognition/package.json", { paths: [ROOT] }),
        );
        const p = path.join(pkg, "ios", path.basename(rel));
        if (fs.existsSync(p)) out.push(p);
      }
    } catch {
      /* package not installed */
    }
  }
  return [...new Set(out)];
}

function patchSource(src) {
  // Undo prior bad rewrite of the enum switch arm.
  let next = src.replace(
    /case\s+\.allowBluetoothHFP\s*:\s*return\s+\.allowBluetoothHFP/g,
    "case .allowBluetooth: return .allowBluetoothHFP",
  );

  // Map enum → AVAudioSession: keep case label, update return value only.
  next = next.replace(
    /case\s+\.allowBluetooth\s*:\s*return\s+\.allowBluetooth(?!A2DP|HFP)\b/g,
    "case .allowBluetooth: return .allowBluetoothHFP",
  );

  // Line-based: rewrite .allowBluetooth → .allowBluetoothHFP except enum decls /
  // case labels that are NOT return mappings.
  next = next
    .split("\n")
    .map((line) => {
      const t = line.trimStart();
      // `case allowBluetooth` (enum member declaration)
      if (/^case\s+allowBluetooth\b/.test(t) && !t.includes("return")) return line;
      // `case .allowBluetooth:` switch label without a return on the same line
      if (/^case\s+\.allowBluetooth\b/.test(t) && !/return/.test(line)) return line;
      // Already correct mapping
      if (/case\s+\.allowBluetooth\s*:\s*return\s+\.allowBluetoothHFP/.test(line)) return line;
      return line.replace(/\.allowBluetooth(?!A2DP|HFP)\b/g, ".allowBluetoothHFP");
    })
    .join("\n");

  return next;
}

function main() {
  const files = resolvePaths();
  if (!files.length) {
    console.log("patch-allow-bluetooth-hfp-ios: targets not installed — skip");
    return;
  }

  let patched = 0;
  for (const file of files) {
    const before = fs.readFileSync(file, "utf8");
    const after = patchSource(before);
    if (after === before) {
      console.log(`patch-allow-bluetooth-hfp-ios: already ok ${path.basename(file)}`);
      continue;
    }
    fs.writeFileSync(file, after);
    patched += 1;
    console.log(`patch-allow-bluetooth-hfp-ios: patched ${path.basename(file)}`);
  }
  if (!patched) {
    console.log("patch-allow-bluetooth-hfp-ios: nothing to change");
  }
}

main();
