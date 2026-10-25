import { FALLBACK, STRINGS } from "../i18n/strings";
import { LANGUAGES } from "../i18n/languages";

const PLACEHOLDER = /\{[A-Za-z0-9_]+\}/g;
const ENGLISH_VARIETIES = new Set(["en", "en-GB", "en-AU", "en-SG"]);

describe("UI string coverage", () => {
  const keys = Object.keys(FALLBACK);

  test.each(LANGUAGES.filter((l) => !ENGLISH_VARIETIES.has(l.code)).map((l) => l.code))("%s has (almost) every key", (code) => {
    const dict = (STRINGS as Record<string, Record<string, string>>)[code];
    const missing = keys.filter((k) => !dict[k]);
    // A handful of keys are deliberately language-neutral; everything else must be translated (by hand or by the machine layer).
    expect(missing.length).toBeLessThanOrEqual(Math.ceil(keys.length * 0.02));
  });

  test.each(LANGUAGES.filter((l) => !ENGLISH_VARIETIES.has(l.code)).map((l) => l.code))("%s keeps every {placeholder} from English", (code) => {
    const dict = (STRINGS as Record<string, Record<string, string>>)[code];
    const broken = keys.filter((k) => dict[k] && [...(FALLBACK as Record<string, string>)[k].matchAll(PLACEHOLDER)].map((m) => m[0]).sort().join() !== [...dict[k].matchAll(PLACEHOLDER)].map((m) => m[0]).sort().join());
    expect(broken).toEqual([]);
  });

  test("right-to-left languages are flagged", () => {
    for (const code of ["ar", "he", "fa", "ur"]) expect(LANGUAGES.find((l) => l.code === code)?.rtl).toBe(true);
  });
});
