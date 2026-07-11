// Global test setup for the jest-expo unit tier.

// Official in-memory AsyncStorage mock (storage.ts persists here in tests).
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);

// expo-constants: config.ts reads Constants.expoConfig.extra at module load.
// Individual tests that need specific `extra` values override this via
// jest.doMock after jest.resetModules (see config.test.ts).
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { extra: {} } },
}));

// Silence the noisy native-module "not linked" warnings the app logs when
// optional modules (speech, sensors) are absent in the JS-only test env.
jest.spyOn(console, "warn").mockImplementation(() => {});
