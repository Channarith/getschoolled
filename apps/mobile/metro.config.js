// Metro bundler config. Block project build artifacts only — NOT node_modules/*/dist
// (e.g. memoize-one lives in node_modules/memoize-one/dist/).
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");
const exclusionList = require("metro-config/src/defaults/exclusionList");

const config = getDefaultConfig(__dirname);
const escape = (s) => s.replace(/[/\\]/g, "[/\\\\]");
const root = escape(path.resolve(__dirname));

config.resolver.blockList = exclusionList([
  config.resolver.blockList,
  new RegExp(`${root}[/\\\\]dist[/\\\\].*`),
  new RegExp(`${root}[/\\\\]\\.expo[/\\\\].*`),
  new RegExp(`${root}[/\\\\]android[/\\\\].*`),
  new RegExp(`${root}[/\\\\]ios[/\\\\].*`),
  // Trim Metro crawl of native/test trees inside dependencies (Mac OOM).
  new RegExp(`${root}[/\\\\]node_modules[/\\\\][^/\\\\]+[/\\\\]android[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\][^/\\\\]+[/\\\\]ios[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\]react-native[/\\\\]ReactAndroid[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\].*[/\\\\]\\.git[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\].*[/\\\\](__tests__|tests?|docs|examples?|coverage)[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\].*\\.md$`),
]);

config.watchFolders = [path.resolve(__dirname)];

// Belt-and-suspenders: pin @babel/runtime even if node_modules still symlinks to ~/pnpm.
try {
  const babelRuntimeRoot = path.dirname(
    require.resolve("@babel/runtime/package.json", { paths: [__dirname] }),
  );
  config.resolver.extraNodeModules = {
    ...(config.resolver.extraNodeModules || {}),
    "@babel/runtime": babelRuntimeRoot,
  };
  if (!babelRuntimeRoot.startsWith(path.resolve(__dirname))) {
    config.watchFolders = [...config.watchFolders, babelRuntimeRoot];
  }
} catch {
  // mobile-deps_ensure_babel_runtime copies a local tree before Metro starts.
}

// Broken Watchman (common on Mac) yields incomplete file maps → Metro 500 on
// @babel/runtime. Node filesystem crawl is slower but reliable for local dev.
config.resolver.useWatchman = false;
config.watcher = {
  ...config.watcher,
  healthCheck: { enabled: false },
};

module.exports = config;
