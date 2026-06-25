/**
 * Patch expo-localization for Xcode 26+ (iOS 26 calendar identifiers).
 * SDK 51 ships expo-localization@15.x without iOS 26 Calendar.Identifier cases.
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

const INSERT = `    case .bangla:
      return "bengali"
    case .gujarati:
      return "gujarati"
    case .kannada:
      return "kannada"
    case .malayalam:
      return "malayalam"
    case .marathi:
      return "marathi"
    case .odia:
      return "odia"
    case .tamil:
      return "tamil"
    case .telugu:
      return "telugu"
    case .vikram:
      return "sanskrit"
    case .dangi:
      return "dangi"
    case .vietnamese:
      return "vietnamese"
    @unknown default:
      return "iso8601"`;

const SEARCH = `    case .iso8601:
      return "iso8601"
    }`;

const REPLACEMENT = `    case .iso8601:
      return "iso8601"
${INSERT}
    }`;

function main() {
  if (!fs.existsSync(swiftPath)) {
    console.log("patch-expo-localization-ios: expo-localization not installed — skip");
    return;
  }

  const src = fs.readFileSync(swiftPath, "utf8");
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
  console.log("patch-expo-localization-ios: added iOS 26 calendar cases to LocalizationModule.swift");
}

main();
