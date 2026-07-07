/**
 * Xcode 26 + pnpm/CocoaPods dual header paths: #pragma once does not dedupe when
 * jsinspector-modern headers are included via Pods/Headers/Private and via
 * node_modules source (redefinition of UniqueMonostate, ExecutionContext, etc.).
 * Add classic include guards to every jsinspector-modern header (RN 0.74.x).
 */
const fs = require("fs");
const path = require("path");

const root = path.join(
  __dirname,
  "..",
  "node_modules",
  "react-native",
  "ReactCommon",
  "jsinspector-modern",
);

function guardName(fileName) {
  const stem = fileName.replace(/\.h$/i, "").replace(/[^A-Za-z0-9]/g, "_");
  return `REACT_JSINSPECTOR_${stem.toUpperCase()}_H`;
}

function patchHeader(fileName) {
  const filePath = path.join(root, fileName);
  if (!fs.existsSync(filePath)) {
    return false;
  }
  let src = fs.readFileSync(filePath, "utf8");
  const guard = guardName(fileName);
  if (src.includes(`#ifndef ${guard}`)) {
    return false;
  }
  if (!src.includes("#pragma once")) {
    return false;
  }
  src = src.replace(
    "#pragma once\n",
    `#pragma once\n#ifndef ${guard}\n#define ${guard}\n`,
  );
  if (!src.trimEnd().endsWith(`#endif // ${guard}`)) {
    src = `${src.trimEnd()}\n\n#endif // ${guard}\n`;
  }
  fs.writeFileSync(filePath, src);
  console.log(`patch-react-native-jsinspector-ios: include guard on ${fileName}`);
  return true;
}

function main() {
  if (!fs.existsSync(root)) {
    console.log("patch-react-native-jsinspector-ios: react-native not installed — skip");
    return;
  }

  const headers = fs
    .readdirSync(root)
    .filter((name) => name.endsWith(".h") && !name.startsWith("."));

  let patched = 0;
  for (const fileName of headers) {
    if (patchHeader(fileName)) {
      patched += 1;
    }
  }

  if (patched === 0) {
    console.log("patch-react-native-jsinspector-ios: already patched");
  } else {
    console.log(`patch-react-native-jsinspector-ios: patched ${patched} header(s)`);
  }
}

main();
