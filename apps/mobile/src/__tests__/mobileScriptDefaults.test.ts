export {};

declare const __dirname: string;
declare function require(name: string): any;

const fs = require("fs");
const path = require("path");

const mobileRoot = path.resolve(__dirname, "../..");

describe("mobile script defaults", () => {
  it("uses the HTTPS API failover instead of the retired HTTP IP", () => {
    for (const rel of ["scripts/mobile-env.sh", "scripts/mobile-check-backends.sh"]) {
      const src = fs.readFileSync(path.join(mobileRoot, rel), "utf8");
      expect(src).toContain("https://api.salareen.com");
      expect(src).not.toContain("http://45.63.91.80");
    }
  });
});
