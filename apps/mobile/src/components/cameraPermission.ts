/** Runtime camera permission for live-class webcam publish. */

import { PermissionsAndroid, Platform } from "react-native";

/**
 * Ensure the OS will allow LiveKit to open the camera.
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
        title: "Camera for live class",
        message: "Salareen needs the camera so classmates can see you in the live room.",
        buttonPositive: "Allow",
        buttonNegative: "Not now",
      },
    );
    return result === PermissionsAndroid.RESULTS.GRANTED;
  } catch {
    return false;
  }
}
