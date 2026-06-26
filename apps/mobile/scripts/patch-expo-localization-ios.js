/**
 * Patch expo-localization for Swift Calendar.Identifier exhaustiveness.
 * Uses @unknown default only — works on EAS (Xcode 16) and local Xcode 26.
 * Do NOT add explicit .bangla/.dangi/etc. cases; those exist only on iOS 26 SDK.
 */
const fs = require("fs");
const path = require("path");

const swiftPath = path.join(
  __dirname,
  "..",
  "node_modules",
  "expo-localization",
  "ios",
  "LocalizationModule.swift",
);

const MARKER = "@unknown default:";

const MINIMAL_INSERT = `    @unknown default:
      return "iso8601"`;

const SEARCH = `    case .iso8601:
      return "iso8601"
    }`;

const REPLACEMENT = `    case .iso8601:
      return "iso8601"
${MINIMAL_INSERT}
    }`;

// Older patch versions added iOS-26-only enum cases that break Xcode 16 / EAS.
const IOS26_ONLY_CASES = /    case \.bangla:[\s\S]*?    @unknown default:\n      return "iso8601"/;

function main() {
  if (!fs.existsSync(swiftPath)) {
    console.log("patch-expo-localization-ios: expo-localization not installed — skip");
    return;
  }

  let src = fs.readFileSync(swiftPath, "utf8");

  if (src.includes("case .bangla:")) {
    src = src.replace(IOS26_ONLY_CASES, MINIMAL_INSERT);
    fs.writeFileSync(swiftPath, src);
    console.log(
      "patch-expo-localization-ios: removed iOS-26-only calendar cases (EAS/Xcode 16 compat)",
    );
    return;
  }

  if (src.includes(MARKER)) {
    console.log("patch-expo-localization-ios: already patched");
    return;
  }

  if (!src.includes(SEARCH)) {
    console.error(
      "patch-expo-localization-ios: unexpected LocalizationModule.swift — manual patch required",
    );
    process.exit(1);
  }

  fs.writeFileSync(swiftPath, src.replace(SEARCH, REPLACEMENT));
  console.log("patch-expo-localization-ios: added @unknown default to LocalizationModule.swift");
}

main();
