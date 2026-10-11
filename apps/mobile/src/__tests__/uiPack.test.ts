import { STRINGS } from "../i18n/strings";

const PLACEHOLDER = /\{[A-Za-z0-9_]+\}/g;

describe("Chinese, Cantonese, and Khmer UI", () => {
  const english = STRINGS.en;

  test("covers every English screen string", () => {
    for (const code of ["zh", "yue", "km"] as const) {
      const table = STRINGS[code];
      for (const key of Object.keys(english) as (keyof typeof english)[]) {
        const line = table[key] ?? "";
        const source = english[key] ?? "";
        expect(line.trim()).toBeTruthy();
        const needed = (source.match(PLACEHOLDER) || []).sort();
        const got = (line.match(PLACEHOLDER) || []).sort();
        expect(got).toEqual(needed);
      }
    }
  });
});
