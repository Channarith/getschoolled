/**
 * Suppress Hermes undeclared-global warnings in Android release builds.
 *
 * The Android Gradle build compiles the JS bundle with hermesc via the
 * createBundle* tasks. hermesc warns on every browser/RN global (fetch,
 * setTimeout, RTCPeerConnection, …) that isn't lexically declared in the
 * function scope where it's used — all of these come from third-party
 * libraries and are expected globals at runtime. They are not actionable.
 *
 * React Native surfaces this via `hermesFlags` in android/app/build.gradle.
 * We append "-w" (disable all Hermes warnings) there so the Android build
 * is as quiet as iOS (where patch-hermesc-quiet-warnings.js does the same).
 */
const fs = require("fs");
const path = require("path");

const BUILD_GRADLE = path.join(__dirname, "..", "android", "app", "build.gradle");

const MARKER = "// hermesc-quiet-warnings: patched";

function main() {
  if (!fs.existsSync(BUILD_GRADLE)) {
    console.log("patch-android-hermesc-quiet: android/app/build.gradle missing — skip (run prebuild first)");
    return;
  }

  let src = fs.readFileSync(BUILD_GRADLE, "utf8");
  if (src.includes(MARKER)) {
    console.log("patch-android-hermesc-quiet: already patched");
    return;
  }

  // React Native's default hermesFlags line — append -w to the array.
  // Pattern matches both single-line and the common multi-line form.
  const PATTERNS = [
    // hermesFlags: ["-O", "-output-source-map"]
    {
      re: /(hermesFlags\s*:\s*\[)([^\]]*)(\])/,
      replacement: (_, open, flags, close) => {
        const cleaned = flags.trim().replace(/,?\s*$/, "");
        return `${open}${cleaned ? cleaned + ", " : ""}"-w"${close} ${MARKER}`;
      },
    },
    // hermesFlags = ["-O", ...] (Kotlin DSL)
    {
      re: /(hermesFlags\s*=\s*listOf\()([^)]*)(\))/,
      replacement: (_, open, flags, close) => {
        const cleaned = flags.trim().replace(/,?\s*$/, "");
        return `${open}${cleaned ? cleaned + ", " : ""}"-w"${close} ${MARKER}`;
      },
    },
  ];

  let patched = false;
  for (const { re, replacement } of PATTERNS) {
    if (re.test(src)) {
      src = src.replace(re, replacement);
      patched = true;
      break;
    }
  }

  if (!patched) {
    console.log("patch-android-hermesc-quiet: hermesFlags not found in build.gradle — skip");
    return;
  }

  fs.writeFileSync(BUILD_GRADLE, src);
  console.log("patch-android-hermesc-quiet: added -w to hermesFlags");
}

main();
