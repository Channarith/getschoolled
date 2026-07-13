/**
 * Xcode 15+/26 + macOS Sequoia: expo-configure-project.sh is written by Node/Expo
 * with com.apple.provenance xattr. Xcode build phases then fail with:
 *   bash: .../expo-configure-project.sh: Operation not permitted
 *
 * Fix:
 * 1) Strip provenance/quarantine xattrs from Pods shell scripts.
 * 2) Rewrite [Expo] Configure project to pipe script contents into bash -c
 *    (avoids execve on the flagged file path).
 * 3) Ensure ENABLE_USER_SCRIPT_SANDBOXING=NO on the app target.
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.join(__dirname, "..");
const IOS = path.join(ROOT, "ios");
const PBX = path.join(IOS, "Salareen.xcodeproj", "project.pbxproj");
const PHASE_NAME = "[Expo] Configure project";
const MARKER = "EXPO_CFG=\"${PODS_ROOT}/Target Support Files/Pods-${TARGET_NAME}/expo-configure-project.sh\"";

const SHELL_SCRIPT = `# This script configures Expo modules and generates the modules provider file.
# Workaround: cat script into bash -c to avoid macOS "Operation not permitted" on provenance xattr.
EXPO_CFG="\${PODS_ROOT}/Target Support Files/Pods-\${TARGET_NAME}/expo-configure-project.sh"
bash -l -c "$(cat "$EXPO_CFG")"
`;

function stripShellScriptXattrs() {
  const podsRoot = path.join(IOS, "Pods");
  if (!fs.existsSync(podsRoot)) {
    return 0;
  }

  let stripped = 0;
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.endsWith(".sh")) {
        try {
          execFileSync("xattr", ["-c", full], { stdio: "ignore" });
          stripped += 1;
        } catch {
          // Non-fatal: xattr may be unavailable on non-macOS CI.
        }
      }
    }
  };
  walk(podsRoot);
  return stripped;
}

function escapePbxShellScript(script) {
  return script.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n");
}

function patchPbxproj() {
  if (!fs.existsSync(PBX)) {
    console.log("patch-ios-expo-configure-project: ios project missing — skip");
    return;
  }

  let src = fs.readFileSync(PBX, "utf8");
  if (src.includes(MARKER)) {
    console.log("patch-ios-expo-configure-project: already patched");
  } else {
    const phaseIdx = src.indexOf(`name = "${PHASE_NAME}";`);
    if (phaseIdx < 0) {
      console.warn(
        "patch-ios-expo-configure-project: [Expo] Configure project phase not found — skip",
      );
    } else {
      const shellKey = "shellScript = ";
      const shellStart = src.indexOf(shellKey, phaseIdx);
      if (shellStart < 0) {
        throw new Error("patch-ios-expo-configure-project: shellScript key missing");
      }
      const valueStart = shellStart + shellKey.length + 1;
      const valueEnd = src.indexOf('";\n', valueStart);
      if (valueEnd < 0) {
        throw new Error("patch-ios-expo-configure-project: shellScript value not terminated");
      }
      const escaped = escapePbxShellScript(SHELL_SCRIPT);
      src = `${src.slice(0, valueStart)}${escaped}${src.slice(valueEnd)}`;
      fs.writeFileSync(PBX, src);
      console.log("patch-ios-expo-configure-project: patched [Expo] Configure project phase");
    }
  }

  let updated = src;
  updated = updated.replace(
    /ENABLE_USER_SCRIPT_SANDBOXING = YES;/g,
    "ENABLE_USER_SCRIPT_SANDBOXING = NO;",
  );
  if (updated !== src) {
    fs.writeFileSync(PBX, updated);
    console.log("patch-ios-expo-configure-project: disabled user script sandboxing");
  }
}

function main() {
  if (process.platform !== "darwin") {
    console.log("patch-ios-expo-configure-project: non-macOS — skip");
    return;
  }

  const stripped = stripShellScriptXattrs();
  if (stripped > 0) {
    console.log(`patch-ios-expo-configure-project: cleared xattrs on ${stripped} shell script(s)`);
  }
  patchPbxproj();
}

main();
