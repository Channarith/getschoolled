/**
 * Lazy optional native module loading — avoids crashing in Expo Go when a
 * config-plugin / dev-client module is not in the host binary.
 */
import { NativeModules } from "react-native";

export function hasExpoNativeModule(name: string): boolean {
  return Boolean((NativeModules as Record<string, unknown>)[name]);
}

export function tryRequireModule<T>(moduleId: string): T | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require(moduleId) as T;
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
