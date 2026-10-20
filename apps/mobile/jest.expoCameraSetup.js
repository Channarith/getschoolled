// Registered before test imports so screens can load without the native camera.
jest.mock("expo-camera", () => ({
  CameraView: () => null,
  Camera: {
    requestCameraPermissionsAsync: jest.fn(async () => ({
      granted: true,
      canAskAgain: true,
      status: "granted",
      expires: "never",
    })),
    getCameraPermissionsAsync: jest.fn(async () => ({
      granted: true,
      canAskAgain: true,
      status: "granted",
      expires: "never",
    })),
  },
}), { virtual: true });
