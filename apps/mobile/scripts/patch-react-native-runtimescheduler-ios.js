/**
 * Xcode 26: #pragma once fails when RuntimeScheduler.h is included twice via
 * different paths (quoted source vs <react/renderer/runtimescheduler/...> Pods).
 * Add classic include guards (same approach as RN codegen PR #44005).
 */
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "node_modules", "react-native", "ReactCommon", "react", "renderer", "runtimescheduler");

const GUARD = "REACT_RUNTIME_SCHEDULER_H";

function patchHeader(fileName) {
  const filePath = path.join(root, fileName);
  if (!fs.existsSync(filePath)) {
    return false;
  }
  let src = fs.readFileSync(filePath, "utf8");
  if (src.includes(`#ifndef ${GUARD}`)) {
    return false;
  }
  if (!src.includes("#pragma once")) {
    console.error(`patch-react-native-runtimescheduler-ios: ${fileName} missing #pragma once`);
    return false;
  }
  src = src.replace(
    "#pragma once\n",
    `#pragma once\n#ifndef ${GUARD}\n#define ${GUARD}\n`,
  );
  if (!src.trimEnd().endsWith(`#endif // ${GUARD}`)) {
    src = `${src.trimEnd()}\n\n#endif // ${GUARD}\n`;
  }
  fs.writeFileSync(filePath, src);
  console.log(`patch-react-native-runtimescheduler-ios: include guard on ${fileName}`);
  return true;
}

function patchRuntimeSchedulerCpp() {
  const filePath = path.join(root, "RuntimeScheduler.cpp");
  if (!fs.existsSync(filePath)) {
    return false;
  }
  let src = fs.readFileSync(filePath, "utf8");
  const marker = "// salareen-xcode26-runtimescheduler-includes";
  if (src.includes(marker)) {
    return false;
  }
  const before = `#include "RuntimeScheduler.h"
#include "RuntimeScheduler_Legacy.h"
#include "RuntimeScheduler_Modern.h"
#include "SchedulerPriorityUtils.h"`;
  const after = `${marker}
#include <react/renderer/runtimescheduler/RuntimeScheduler.h>
#include <react/renderer/runtimescheduler/RuntimeScheduler_Legacy.h>
#include <react/renderer/runtimescheduler/RuntimeScheduler_Modern.h>
#include <react/renderer/runtimescheduler/SchedulerPriorityUtils.h>`;
  if (!src.includes(before)) {
    return false;
  }
  fs.writeFileSync(filePath, src.replace(before, after));
  console.log("patch-react-native-runtimescheduler-ios: unified angle-bracket includes in RuntimeScheduler.cpp");
  return true;
}

function main() {
  if (!fs.existsSync(root)) {
    console.log("patch-react-native-runtimescheduler-ios: react-native not installed — skip");
    return;
  }
  let patched = false;
  patched = patchHeader("RuntimeScheduler.h") || patched;
  patched = patchRuntimeSchedulerCpp() || patched;
  if (!patched) {
    console.log("patch-react-native-runtimescheduler-ios: already patched");
  }
}

main();
