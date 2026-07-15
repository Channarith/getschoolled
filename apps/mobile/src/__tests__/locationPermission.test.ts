import {
  __resetLocationPermissionCacheForTests,
  ensureForegroundLocationPermission,
} from "../locationPermission";

type LocationModule = typeof import("expo-location");

function mockLocation(over: Partial<Record<string, jest.Mock>>): LocationModule {
  return {
    getForegroundPermissionsAsync: jest.fn(),
    requestForegroundPermissionsAsync: jest.fn(),
    ...over,
  } as unknown as LocationModule;
}

describe("ensureForegroundLocationPermission", () => {
  beforeEach(() => __resetLocationPermissionCacheForTests());  // clear session grant cache
  it("returns true WITHOUT prompting when already granted (Apple: check status first)", async () => {
    const req = jest.fn();
    const Location = mockLocation({
      getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted", canAskAgain: true }),
      requestForegroundPermissionsAsync: req,
    });
    await expect(ensureForegroundLocationPermission(Location)).resolves.toBe(true);
    expect(req).not.toHaveBeenCalled();
  });

  it("prompts only when the status is undetermined", async () => {
    const req = jest.fn().mockResolvedValue({ status: "granted" });
    const Location = mockLocation({
      getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "undetermined", canAskAgain: true }),
      requestForegroundPermissionsAsync: req,
    });
    await expect(ensureForegroundLocationPermission(Location)).resolves.toBe(true);
    expect(req).toHaveBeenCalledTimes(1);
  });

  it("returns false WITHOUT prompting when denied and the OS won't ask again", async () => {
    const req = jest.fn();
    const Location = mockLocation({
      getForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "denied", canAskAgain: false }),
      requestForegroundPermissionsAsync: req,
    });
    await expect(ensureForegroundLocationPermission(Location)).resolves.toBe(false);
    expect(req).not.toHaveBeenCalled();
  });

  it("degrades to false if the native module throws", async () => {
    const Location = mockLocation({
      getForegroundPermissionsAsync: jest.fn().mockRejectedValue(new Error("boom")),
    });
    await expect(ensureForegroundLocationPermission(Location)).resolves.toBe(false);
  });

  it("caches a granted result so a re-mount does NOT re-probe CoreLocation", async () => {
    const getPerms = jest.fn().mockResolvedValue({ status: "granted", canAskAgain: true });
    const Location = mockLocation({ getForegroundPermissionsAsync: getPerms });
    await expect(ensureForegroundLocationPermission(Location)).resolves.toBe(true);
    await expect(ensureForegroundLocationPermission(Location)).resolves.toBe(true);
    // Second call short-circuits from the session cache — no second native probe
    // (this is what stops the CoreLocation diagnostic from recurring per mount).
    expect(getPerms).toHaveBeenCalledTimes(1);
  });
});
