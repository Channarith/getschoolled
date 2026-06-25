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
  // Trim Metro crawl of native/test trees inside dependencies (Mac OOM on export).
  new RegExp(`${root}[/\\\\]node_modules[/\\\\][^/\\\\]+[/\\\\]android[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\][^/\\\\]+[/\\\\]ios[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\]react-native[/\\\\]ReactAndroid[/\\\\].*`),
  new RegExp(`${root}[/\\\\]node_modules[/\\\\].*[/\\\\]\\.git[/\\\\].*`),
]);

config.watchFolders = [path.resolve(__dirname)];

module.exports = config;
