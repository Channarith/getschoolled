import { isTrustedNavigation } from "../webNavigation";

const BASE = "https://salareen.com";

describe("isTrustedNavigation", () => {
  it("allows our own pages", () => {
    for (const u of ["https://salareen.com/demo/drivers-ed", "https://www.salareen.com/", "https://api.salareen.com/x?y=1", "about:blank"]) {
      expect(isTrustedNavigation(u, BASE)).toBe(true);
    }
  });

  it("refuses every other site, including look-alikes and tricks", () => {
    for (const u of [
      "https://evil.example/", "https://salareen.com.evil.example/", "https://evilsalareen.com/", "https://salareen.com@evil.example/", "https://salareen.com:443@evil.example/", "https://user:pw@evil.example/",
      "https://evil.example/?next=https://salareen.com", "http://salareen.com/", "javascript:alert(1)", "data:text/html,x", "file:///etc/passwd",
      "intent://x#Intent;end", "", "//evil.example/",
    ]) {
      expect(isTrustedNavigation(u, BASE)).toBe(false);
    }
  });

  it("follows a configured app host, plain http only when the build itself points at plain http", () => {
    expect(isTrustedNavigation("https://staging.example.org/demo", "https://staging.example.org")).toBe(true);
    expect(isTrustedNavigation("http://192.168.1.50:3000/demo", "http://192.168.1.50:3000")).toBe(true);
    expect(isTrustedNavigation("http://192.168.1.50:3000/demo", BASE)).toBe(false);
  });
});
