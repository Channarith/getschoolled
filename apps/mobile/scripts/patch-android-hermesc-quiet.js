/**
 * Suppress Hermes undeclared-global warnings in Android release builds.
 *
 * The Android Gradle build compiles the JS bundle with hermesc via the
 * createBundle* tasks. hermesc warns on every browser/RN global (fetch,
 * setTimeout, RTCPeerConnection, …) that isn't lexically declared in the
 * function scope where it's used — all of these come from third-party
 * libraries and are expected globals at runtime. They are not actionable.
 *
 * Expo prebuild writes android/app/build.gradle with hermesFlags commented
 * out, so this script inserts an active flag list that keeps the React
 * Native defaults and adds "-w" (disable Hermes warnings).
 */
const fs = require("fs");
const path = require("path");

const ANDROID = path.join(__dirname, "..", "android");
const APP_GRADLE = path.join(ANDROID, "app", "build.gradle");
const ROOT_GRADLE = path.join(ANDROID, "build.gradle");

const HERMES_MARKER = "// hermesc-quiet-warnings: patched";
const JAVAC_MARKER = "// javac-quiet-notes: patched";
const HERMES_FLAGS = 'hermesFlags = ["-O", "-output-source-map", "-w"]';

function patchHermesFlags() {
  if (!fs.existsSync(APP_GRADLE)) {
    console.log("patch-android-hermesc-quiet: android/app/build.gradle missing — skip (run prebuild first)");
    return;
  }
  let src = fs.readFileSync(APP_GRADLE, "utf8");
  if (src.includes(HERMES_MARKER) && /hermesFlags\s*=\s*\[[^\]]*"-w"/.test(src)) {
    console.log("patch-android-hermesc-quiet: hermesFlags already patched");
    return;
  }

  const active = src.match(/^(\s*)hermesFlags\s*=\s*\[([^\]]*)\]/m);
  if (active && !active[0].trim().startsWith("//")) {
    const indent = active[1];
    const flags = active[2].includes('"-w"') ? active[2] : `${active[2].trim().replace(/,\s*$/, "")}, "-w"`;
    src = src.replace(active[0], `${indent}hermesFlags = [${flags}] ${HERMES_MARKER}`);
  } else {
    const anchor = /^(\s*)hermesCommand\s*=.*$/m;
    if (!anchor.test(src)) {
      console.log("patch-android-hermesc-quiet: hermesCommand not found in build.gradle — skip");
      return;
    }
    src = src.replace(anchor, (line) => `${line}\n    ${HERMES_FLAGS} ${HERMES_MARKER}`);
  }
  fs.writeFileSync(APP_GRADLE, src);
  console.log("patch-android-hermesc-quiet: added -w to hermesFlags");
}

function patchJavacNotes() {
  if (!fs.existsSync(ROOT_GRADLE)) return;
  let src = fs.readFileSync(ROOT_GRADLE, "utf8");
  if (src.includes(JAVAC_MARKER)) {
    console.log("patch-android-hermesc-quiet: javac notes already patched");
    return;
  }
  src += `
${JAVAC_MARKER}
subprojects { subproject ->
    subproject.tasks.withType(JavaCompile).configureEach {
        options.compilerArgs.add("-nowarn")
    }
}
`;
  fs.writeFileSync(ROOT_GRADLE, src);
  console.log("patch-android-hermesc-quiet: suppressed dependency javac notes");
}

patchHermesFlags();
patchJavacNotes();
