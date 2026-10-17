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

// @expo/vector-icons pulls expo-asset/expo-font, which need the native runtime
// and throw under the JS-only test env. Stub every icon set to a plain host
// element (a Proxy returns the same stub for Ionicons, AntDesign, etc.) so
// components that render icons can still be tested for structure/testIDs.
jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  const Icon = (props) => React.createElement(Text, props, null);
  return new Proxy({}, { get: () => Icon });
});

// expo-linear-gradient renders a native view; a plain View is enough for tests.
jest.mock("expo-linear-gradient", () => {
  const { View } = require("react-native");
  return { LinearGradient: View };
});

jest.mock("react-native-safe-area-context", () => {
  const React = require("react");
  const { View } = require("react-native");
  const insets = { top: 0, right: 0, bottom: 0, left: 0 };
  return {
    SafeAreaProvider: ({ children }) => children,
    SafeAreaView: View,
    useSafeAreaInsets: () => insets,
    useSafeAreaFrame: () => ({ x: 0, y: 0, width: 390, height: 844 }),
    initialWindowMetrics: { insets, frame: { x: 0, y: 0, width: 390, height: 844 } },
  };
});

// Silence the noisy native-module "not linked" warnings the app logs when
// optional modules (speech, sensors) are absent in the JS-only test env.
jest.spyOn(console, "warn").mockImplementation(() => {});
