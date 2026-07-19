/**
 * U-CFG-1 — backend URL resolution (QA V&V plan, Mobile dimension).
 *
 * config.ts computes service URLs once at module load from Platform.OS +
 * expo-constants `extra`. We reload the module under controlled mocks to cover
 * the ios/android x local/cloud x host-rewrite matrix, plus the cloud failover
 * mapping and the QA-account posture that keeps admin creds out of prod bundles.
 */

type Extra = Record<string, unknown>;

// Reload config.ts with a specific Platform.OS and expo-constants `extra`.
function loadConfig(os: "ios" | "android", extra: Extra) {
  jest.resetModules();
  jest.doMock("react-native", () => ({ Platform: { OS: os } }));
  jest.doMock("expo-constants", () => ({
    __esModule: true,
    default: { expoConfig: { extra } },
  }));
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require("../config") as typeof import("../config");
}

afterEach(() => {
  jest.dontMock("react-native");
  jest.dontMock("expo-constants");
});

describe("cloud mode (default)", () => {
  test("resolves service paths against www.salareen.com", () => {
    const c = loadConfig("ios", {});
    expect(c.DEPLOY_MODE).toBe("cloud");
    expect(c.CURRICULUM_URL).toBe("https://www.salareen.com/curriculum");
    expect(c.IDENTITY_URL).toBe("https://www.salareen.com/identity");
    expect(c.MEMORY_URL).toBe("https://www.salareen.com/memory");
    // orchestrator has an empty service path -> bare origin.
    expect(c.ORCHESTRATOR_URL).toBe("https://www.salareen.com");
  });

  test("rejects a configured localhost URL and falls back to the cloud origin", () => {
    const c = loadConfig("ios", { curriculumUrl: "http://localhost:8005" });
    // A localhost override must never win in cloud mode (would point a shipped
    // build at a dev machine).
    expect(c.CURRICULUM_URL).toBe("https://www.salareen.com/curriculum");
  });

  test("honors a cloudBaseUrl override", () => {
    const c = loadConfig("android", { cloudBaseUrl: "https://staging.salareen.com/" });
    expect(c.CLOUD_BASE_URL).toBe("https://staging.salareen.com");
    expect(c.CURRICULUM_URL).toBe("https://staging.salareen.com/curriculum");
  });

  test("failoverUrlFor maps a primary cloud URL to the Vultr twin", () => {
    const c = loadConfig("ios", {});
    expect(c.failoverUrlFor("https://www.salareen.com/curriculum")).toBe(
      "https://api.salareen.com/curriculum",
    );
    // A URL outside the primary origin has no failover twin.
    expect(c.failoverUrlFor("https://example.com/x")).toBeNull();
  });
});

describe("local mode (emulator/simulator host rewrite)", () => {
  test("iOS simulator uses localhost", () => {
    const c = loadConfig("ios", { deployMode: "local" });
    expect(c.DEPLOY_MODE).toBe("local");
    expect(c.CURRICULUM_URL).toBe("http://localhost:8005");
    expect(c.IDENTITY_URL).toBe("http://localhost:8008");
  });

  test("Android emulator rewrites localhost to 10.0.2.2", () => {
    const c = loadConfig("android", { deployMode: "local" });
    expect(c.CURRICULUM_URL).toBe("http://10.0.2.2:8005");
    expect(c.MEMORY_URL).toBe("http://10.0.2.2:8004");
  });

  test("Android rewrites a configured localhost service URL", () => {
    const c = loadConfig("android", {
      deployMode: "local",
      curriculumUrl: "http://localhost:9999",
    });
    expect(c.CURRICULUM_URL).toBe("http://10.0.2.2:9999");
  });

  test("failover is disabled in local mode", () => {
    const c = loadConfig("ios", { deployMode: "local" });
    expect(c.failoverUrlFor("http://localhost:8005")).toBeNull();
  });
});

describe("QA test accounts (B-SEC-1 posture)", () => {
  test("empty when extra provides none (production bundle carries no creds)", () => {
    const c = loadConfig("ios", {});
    expect(c.QA_TEST_ACCOUNTS).toEqual([]);
  });

  test("populated from extra for dev/preview builds", () => {
    const accounts = [{ label: "QA Pro", email: "qa-pro@salareen.com", password: "QaTest123" }];
    const c = loadConfig("ios", { qaTestAccounts: accounts });
    expect(c.QA_TEST_ACCOUNTS).toEqual(accounts);
  });
});
