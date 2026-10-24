import { compareVersions, decideUpdate, fetchAppVersion } from "../updateCheck";

const INFO = {
  web: "0.97.12",
  android: { version: "0.97.12", url: "/download/android", min_supported: "0.95.0" },
  ios: { version: "0.97.10", url: "https://testflight.apple.com/join/abc", min_supported: null },
};

describe("update decision", () => {
  it("prompts when a newer android build exists and resolves the relative url", () => {
    const d = decideUpdate("0.97.3", INFO, "android", "", "https://www.salareen.com/");
    expect(d.prompt).toBe(true);
    expect(d.force).toBe(false);
    expect(d.url).toBe("https://www.salareen.com/download/android");
  });

  it("does not prompt when current or newer", () => {
    expect(decideUpdate("0.97.12", INFO, "android").prompt).toBe(false);
    expect(decideUpdate("0.98.0", INFO, "android").prompt).toBe(false);
  });

  it("a dismissed version stays dismissed, unless the build is below the minimum", () => {
    expect(decideUpdate("0.97.3", INFO, "android", "0.97.12").prompt).toBe(false);
    const forced = decideUpdate("0.94.0", INFO, "android", "0.97.12");
    expect(forced.prompt).toBe(true);
    expect(forced.force).toBe(true);
  });

  it("uses the platform's own entry and tolerates missing data", () => {
    expect(decideUpdate("0.97.3", INFO, "ios").url).toBe("https://testflight.apple.com/join/abc");
    expect(decideUpdate("0.97.3", { android: null }, "android").prompt).toBe(false);
    expect(decideUpdate("0.97.3", null, "ios").prompt).toBe(false);
    expect(decideUpdate("0.97.3", INFO, "web").prompt).toBe(false);
  });

  it("compares semantic versions numerically", () => {
    expect(compareVersions("0.97.12", "0.97.2")).toBe(1);
    expect(compareVersions("0.97.2", "0.97.12")).toBe(-1);
  });
});

describe("fetchAppVersion", () => {
  it("returns null on a network error or a bad status, never throws", async () => {
    const down = (async () => { throw new Error("offline"); }) as unknown as typeof fetch;
    const bad = (async () => ({ ok: false, status: 503, json: async () => ({}) })) as unknown as typeof fetch;
    expect(await fetchAppVersion("https://x", down)).toBeNull();
    expect(await fetchAppVersion("https://x", bad)).toBeNull();
  });

  it("returns the parsed body on success", async () => {
    const ok = (async () => ({ ok: true, json: async () => INFO })) as unknown as typeof fetch;
    expect((await fetchAppVersion("https://x/", ok))?.web).toBe("0.97.12");
  });
});
