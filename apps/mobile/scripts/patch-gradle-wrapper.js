const fs = require("fs");
const path = require("path");

const wrapperPath = path.join(
  __dirname,
  "..",
  "android",
  "gradle",
  "wrapper",
  "gradle-wrapper.properties",
);
const reactNativeSettingsPath = path.join(
  __dirname,
  "..",
  "node_modules",
  "@react-native",
  "gradle-plugin",
  "settings.gradle.kts",
);

const defaultUrl =
  "https://github.com/gradle/gradle-distributions/releases/download/v8.8.0/gradle-8.8-all.zip";
const distributionUrl = process.env.GRADLE_DISTRIBUTION_URL || defaultUrl;

if (!fs.existsSync(wrapperPath)) {
  console.error(`Gradle wrapper properties not found: ${wrapperPath}`);
  process.exit(1);
}

const escapedUrl = distributionUrl.replace("https://", "https\\://");
const lines = fs.readFileSync(wrapperPath, "utf8").split(/\r?\n/);
const patched = lines.map((line) =>
  line.startsWith("distributionUrl=") ? `distributionUrl=${escapedUrl}` : line,
);

fs.writeFileSync(wrapperPath, patched.join("\n"));
console.log(`Gradle wrapper distributionUrl set to ${distributionUrl}`);

if (fs.existsSync(reactNativeSettingsPath)) {
  const rnSettings = fs.readFileSync(reactNativeSettingsPath, "utf8");
  const foojayPlugin =
    'plugins { id("org.gradle.toolchains.foojay-resolver-convention").version("0.5.0") }';
  const patchedFoojayPlugin =
    "// Patched by apps/mobile/scripts/patch-gradle-wrapper.js; Java is provided by CI/local env.";
  if (rnSettings.includes(foojayPlugin)) {
    fs.writeFileSync(
      reactNativeSettingsPath,
      rnSettings.replace(foojayPlugin, patchedFoojayPlugin),
    );
    console.log("React Native Foojay toolchain resolver plugin disabled for this build");
  }
}
