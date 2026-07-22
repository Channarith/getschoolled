/**
 * Lazy optional native module loading — avoids crashing in Expo Go when a
 * config-plugin / dev-client module is not in the host binary, and avoids
 * touching BatchedBridge on web (__fbBatchedBridgeConfig).
 */
import { NativeModules, Platform } from "react-native";

export function hasExpoNativeModule(name: string): boolean {
  if (Platform.OS === "web") return false;
  try {
    return Boolean((NativeModules as Record<string, unknown>)[name]);
  } catch {
    return false;
  }
}

// Metro cannot bundle `require(variable)` — the module id must be a string
// literal so it is included in the bundle. Route the known-optional modules
// through literal requires while keeping the dynamic-looking call sites intact.
const OPTIONAL_MODULE_LOADERS: Record<string, () => unknown> = {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  "expo-location": () => require("expo-location"),
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  "expo-sensors": () => require("expo-sensors"),
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  "expo-speech-recognition": () => require("expo-speech-recognition"),
};

export function tryRequireModule<T>(moduleId: string): T | null {
  if (Platform.OS === "web") return null;
  const loader = OPTIONAL_MODULE_LOADERS[moduleId];
  if (!loader) {
    return null;
  }
  try {
    return loader() as T;
  } catch {
    return null;
  }
}

export function isExpoLocationAvailable(): boolean {
  return hasExpoNativeModule("ExpoLocation") || tryRequireModule("expo-location") != null;
}

export function isExpoSensorsAvailable(): boolean {
  return hasExpoNativeModule("ExponentAccelerometer") || tryRequireModule("expo-sensors") != null;
}

export function isExpoSpeechRecognitionAvailable(): boolean {
  return (
    hasExpoNativeModule("ExpoSpeechRecognition")
    || tryRequireModule("expo-speech-recognition") != null
  );
}
