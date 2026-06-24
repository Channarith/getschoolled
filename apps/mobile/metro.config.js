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
  new RegExp(`${root}[/\\\\]android[/\\\\]build[/\\\\].*`),
  new RegExp(`${root}[/\\\\]ios[/\\\\]build[/\\\\].*`),
]);

module.exports = config;
