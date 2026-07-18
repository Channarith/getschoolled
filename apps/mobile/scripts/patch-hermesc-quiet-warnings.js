/**
 * Silence Hermes bytecode-compiler noise during Xcode "Bundle React Native
 * code and images". hermesc warns on every undeclared browser/RN global
 * (fetch, setTimeout, TextDecoder, WebSocket, …) — expected at runtime, not
 * actionable. hermesc supports `-w` (disable all warnings); RN's
 * react-native-xcode.sh does not pass it, so we inject it into EXTRA_COMPILER_ARGS.
 */
const fs = require("fs");
const path = require("path");

function resolveXcodeScript() {
  try {
    const rnRoot = path.dirname(
      require.resolve("react-native/package.json", {
        paths: [path.join(__dirname, "..")],
      }),
    );
    return path.join(rnRoot, "scripts", "react-native-xcode.sh");
  } catch {
    const local = path.join(
      __dirname,
      "..",
      "node_modules",
      "react-native",
      "scripts",
      "react-native-xcode.sh",
    );
    return fs.existsSync(local) ? local : null;
  }
}

const MARKER = "EXTRA_COMPILER_ARGS=\"$EXTRA_COMPILER_ARGS -w\"";

function main() {
  const scriptPath = resolveXcodeScript();
  if (!scriptPath || !fs.existsSync(scriptPath)) {
    console.log("patch-hermesc-quiet-warnings: react-native-xcode.sh missing — skip");
    return;
  }

  let src = fs.readFileSync(scriptPath, "utf8");
  if (src.includes(MARKER) || src.includes("EXTRA_COMPILER_ARGS=\"$EXTRA_COMPILER_ARGS -w\"")) {
    console.log("patch-hermesc-quiet-warnings: already patched");
    return;
  }

  // After RN sets -O / -Og, append -w before hermesc runs.
  const needle =
    '  "$HERMES_CLI_PATH" -emit-binary -max-diagnostic-width=80 $EXTRA_COMPILER_ARGS -out "$DEST/main.jsbundle" "$BUNDLE_FILE"';
  if (!src.includes(needle)) {
    // Broader match for minor RN script drift.
    const alt = /("\$HERMES_CLI_PATH"\s+-emit-binary[^\n]+)/;
    if (!alt.test(src)) {
      console.error(
        "patch-hermesc-quiet-warnings: unexpected react-native-xcode.sh — manual patch required",
      );
      process.exit(1);
    }
    src = src.replace(
      alt,
      '  EXTRA_COMPILER_ARGS="$EXTRA_COMPILER_ARGS -w"\n  $1',
    );
  } else {
    src = src.replace(
      needle,
      '  EXTRA_COMPILER_ARGS="$EXTRA_COMPILER_ARGS -w"\n' + needle,
    );
  }

  fs.writeFileSync(scriptPath, src);
  console.log("patch-hermesc-quiet-warnings: injected hermesc -w");
}

main();
