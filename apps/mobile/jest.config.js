// jest-expo preset: transforms RN/Expo modules and provides the RN test
// environment. Unit tier only (no device) — see QA V&V plan Mobile dimension.
module.exports = {
  preset: "jest-expo",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  // jest-expo ships a transformIgnorePatterns that whitelists expo/RN packages
  // for Babel; extend it with the extra native deps this app pulls in so their
  // ESM sources get transpiled instead of failing to parse.
  transformIgnorePatterns: [
    "node_modules/(?!((jest-)?react-native|@react-native(-community)?|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg|@livekit/.*|livekit-client|react-native-google-mobile-ads))",
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
