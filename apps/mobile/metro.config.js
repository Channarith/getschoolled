// Metro bundler config. Block project build artifacts only — NOT node_modules/*/dist
// (e.g. memoize-one lives in node_modules/memoize-one/dist/).
//
// NOTE: do NOT require("metro-config/...") here. metro-config is a *transitive*
// dependency (via expo -> @expo/cli -> metro); under pnpm's isolated node_modules
// on EAS it is a phantom dependency and require() throws MODULE_NOT_FOUND, which
// breaks `expo export:embed` during the Xcode "Bundle React Native code" phase.
// We build the blockList as a single RegExp using only Expo's default config.
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);
const escape = (s) => s.replace(/[/\\]/g, "[/\\\\]");
const root = escape(path.resolve(__dirname));

const blockPatterns = [
  `${root}[/\\\\]dist[/\\\\].*`,
  `${root}[/\\\\]\\.expo[/\\\\].*`,
  `${root}[/\\\\]android[/\\\\].*`,
  `${root}[/\\\\]ios[/\\\\].*`,
  // Trim Metro crawl of native/test trees inside dependencies (Mac OOM).
  `${root}[/\\\\]node_modules[/\\\\][^/\\\\]+[/\\\\]android[/\\\\].*`,
  `${root}[/\\\\]node_modules[/\\\\][^/\\\\]+[/\\\\]ios[/\\\\].*`,
  `${root}[/\\\\]node_modules[/\\\\]react-native[/\\\\]ReactAndroid[/\\\\].*`,
  `${root}[/\\\\]node_modules[/\\\\].*[/\\\\]\\.git[/\\\\].*`,
  `${root}[/\\\\]node_modules[/\\\\].*[/\\\\](__tests__|tests?|docs|examples?|coverage)[/\\\\].*`,
  `${root}[/\\\\]node_modules[/\\\\].*\\.md$`,
];

// Preserve any blockList regex(es) Expo's default config already set.
const existing = config.resolver.blockList;
const existingSources = [];
if (Array.isArray(existing)) {
  for (const re of existing) {
    if (re && re.source) existingSources.push(re.source);
  }
} else if (existing && existing.source) {
  existingSources.push(existing.source);
}

config.resolver.blockList = new RegExp(
  [...existingSources, ...blockPatterns].map((s) => `(?:${s})`).join("|"),
);

config.watchFolders = [path.resolve(__dirname)];

// Belt-and-suspenders: pin packages Metro/export:embed must resolve under pnpm on EAS.
function pinPackage(config, name) {
  try {
    const pkgRoot = path.dirname(
      require.resolve(`${name}/package.json`, { paths: [__dirname] }),
    );
    config.resolver.extraNodeModules = {
      ...(config.resolver.extraNodeModules || {}),
      [name]: pkgRoot,
    };
    if (!pkgRoot.startsWith(path.resolve(__dirname))) {
      config.watchFolders = [...(config.watchFolders || []), pkgRoot];
    }
  } catch {
    // ensure-metro-local-deps / direct deps should provide a local tree before Metro starts.
  }
}

for (const pkg of [
  "@babel/runtime",
  "expo-asset",
  "@react-native/assets-registry",
]) {
  pinPackage(config, pkg);
}

// Broken Watchman (common on Mac) yields incomplete file maps → Metro 500 on
// @babel/runtime. Node filesystem crawl is slower but reliable for local dev.
config.resolver.useWatchman = false;
config.watcher = {
  ...config.watcher,
  healthCheck: { enabled: false },
};

// Web: never fall back to *.ios.js — that pulls BatchedBridge into the browser
// and crashes with __fbBatchedBridgeConfig. Stub native-only packages instead.
const WEB_STUBS = {
  "react-native-google-mobile-ads": path.resolve(
    __dirname,
    "src/shims/react-native-google-mobile-ads.web.js",
  ),
};
const priorResolveRequest = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (platform === "web" && WEB_STUBS[moduleName]) {
    return { type: "sourceFile", filePath: WEB_STUBS[moduleName] };
  }
  if (typeof priorResolveRequest === "function") {
    return priorResolveRequest(context, moduleName, platform);
  }
  return context.resolveRequest(context, moduleName, platform);
};

module.exports = config;
