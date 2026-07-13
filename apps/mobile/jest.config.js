// jest-expo preset: transforms RN/Expo modules and provides the RN test
// environment. Unit tier only (no device) — see QA V&V plan Mobile dimension.

// RN/Expo packages ship untranspiled Flow/TS/ESM and MUST go through Babel.
// Bare prefixes match both the hoisted (`@react-native/js-polyfills`) and the
// pnpm store (`@react-native+js-polyfills@0.74.87`) folder names. `react-native`
// covers `react-native-svg`, `-google-mobile-ads`, `-web`, …; `expo` covers
// `expo-av`, `expo-asset`, …
const TRANSPILE = [
  "(jest-)?react-native",
  "@react-native",
  "expo",
  "@expo",
  "@expo-google-fonts",
  "react-navigation",
  "@react-navigation",
  "@unimodules",
  "unimodules",
  "sentry-expo",
  "native-base",
  "@livekit",
  "livekit-client",
].join("|");

module.exports = {
  preset: "jest-expo",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  // The previous single pattern assumed a hoisted node_modules. Under pnpm the
  // real path is node_modules/.pnpm/<pkg>@<ver>/node_modules/<pkg>, so the first
  // segment after node_modules/ is ".pnpm" — which the old lookahead treated as
  // "not whitelisted" and force-ignored, leaving RN's Flow files (error-guard.js)
  // untransformed → "Unexpected identifier 'ErrorHandler'". These two patterns
  // handle the pnpm store and the hoisted layout without re-ignoring .pnpm.
  transformIgnorePatterns: [
    `node_modules/\\.pnpm/(?!(${TRANSPILE}))`,
    `node_modules/(?!\\.pnpm/)(?!(${TRANSPILE}))`,
  ],
  testMatch: ["<rootDir>/src/**/__tests__/**/*.test.ts?(x)"],
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/__tests__/**",
    "!src/**/*.d.ts",
  ],
  // Screens (JSX-heavy, component tier) are excluded from the initial coverage
  // floor; the unit tier targets logic modules first (config, storage, driving
  // detection, voice assistant). Raise this as component suites land.
  clearMocks: true,
};
