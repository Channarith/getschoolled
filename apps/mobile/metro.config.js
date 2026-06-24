// Metro bundler config. Keep export/watch scans out of build artifacts.
const { getDefaultConfig } = require("expo/metro-config");
const exclusionList = require("metro-config/src/defaults/exclusionList");

const config = getDefaultConfig(__dirname);

config.resolver.blockList = exclusionList([
  config.resolver.blockList,
  /\/dist\/.*/,
  /\/\.expo\/.*/,
  /\/android\/build\/.*/,
  /\/ios\/build\/.*/,
]);

module.exports = config;
