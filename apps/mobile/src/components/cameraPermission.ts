/** Runtime camera permission for live-class webcam publish. */

import { PermissionsAndroid, Platform } from "react-native";

/**
 * Ensure the OS will allow LiveKit (live class) and the in-app camera games to open the camera.
 * iOS prompts via NSCameraUsageDescription when getUserMedia runs.
 * Android needs an explicit runtime CAMERA grant (API 23+).
 */
export async function ensureCameraPermission(): Promise<boolean> {
  if (Platform.OS !== "android") return true;
  try {
    const existing = await PermissionsAndroid.check(
      PermissionsAndroid.PERMISSIONS.CAMERA,
    );
    if (existing) return true;
    const result = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.CAMERA,
      {
        title: "Camera for live class and camera games",
        message: "Salareen uses the camera for live class video and for camera games that follow your hands and body. Video stays on this phone for the games.",
        buttonPositive: "Allow",
        buttonNegative: "Not now",
      },
    );
    return result === PermissionsAndroid.RESULTS.GRANTED;
  } catch {
    return false;
  }
}
