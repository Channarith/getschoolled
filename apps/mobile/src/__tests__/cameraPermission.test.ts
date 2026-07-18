import { PermissionsAndroid, Platform } from "react-native";

import { ensureCameraPermission } from "../components/cameraPermission";

jest.mock("react-native", () => {
  const check = jest.fn();
  const request = jest.fn();
  return {
    Platform: { OS: "android" },
    PermissionsAndroid: {
      PERMISSIONS: { CAMERA: "android.permission.CAMERA" },
      RESULTS: { GRANTED: "granted", DENIED: "denied" },
      check,
      request,
    },
  };
});

const mockCheck = PermissionsAndroid.check as jest.Mock;
const mockRequest = PermissionsAndroid.request as jest.Mock;

describe("ensureCameraPermission", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Platform as { OS: string }).OS = "android";
  });

  it("returns true on iOS without prompting", async () => {
    (Platform as { OS: string }).OS = "ios";
    await expect(ensureCameraPermission()).resolves.toBe(true);
    expect(mockCheck).not.toHaveBeenCalled();
  });

  it("returns true when Android camera is already granted", async () => {
    mockCheck.mockResolvedValue(true);
    await expect(ensureCameraPermission()).resolves.toBe(true);
    expect(mockRequest).not.toHaveBeenCalled();
  });

  it("requests Android camera permission when missing", async () => {
    mockCheck.mockResolvedValue(false);
    mockRequest.mockResolvedValue(PermissionsAndroid.RESULTS.GRANTED);
    await expect(ensureCameraPermission()).resolves.toBe(true);
    expect(mockRequest).toHaveBeenCalled();
  });

  it("returns false when Android denies camera permission", async () => {
    mockCheck.mockResolvedValue(false);
    mockRequest.mockResolvedValue(PermissionsAndroid.RESULTS.DENIED);
    await expect(ensureCameraPermission()).resolves.toBe(false);
  });
});
