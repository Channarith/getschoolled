import type { VoiceGroup } from "../api";
import { CUSTOM_PREFIX, buildVoiceOptions, clipLangForLocale, customVoiceLabel, distinctVoiceGroups } from "../voicePicker";

const v = (id: string, locale: string, accent: string, label: string, gender: string) =>
  ({ id, locale, accent, label, gender, language: locale.slice(0, 2), dialect: "" });

const groups: VoiceGroup[] = [
  { language: "en", voices: [
    v("en-US-AvaNeural", "en-US", "American", "American — Ava (F)", "female"),
    v("en-US-GuyNeural", "en-US", "American", "American — Guy (M)", "male"),
    v("en-US-GuyNeural#ny", "en-US", "New York", "New York — Guy (M)", "male"),
  ] },
  { language: "km", voices: [v("km-KH-SreymomNeural", "km-KH", "Khmer (Cambodia)", "Khmer — Sreymom (F)", "female")] },
];

test("one option per real voice; the duplicate regional copy is dropped", () => {
  const out = distinctVoiceGroups(groups);
  expect(out[0].voices.map((x) => x.id)).toEqual(["en-US-AvaNeural", "en-US-GuyNeural"]);
});

test("a saved duplicate stays listed so the choice never vanishes", () => {
  const out = distinctVoiceGroups(groups, "en-US-GuyNeural#ny");
  expect(out[0].voices.map((x) => x.id)).toContain("en-US-GuyNeural#ny");
});

test("the dropdown is Default, custom voices, then catalog voices by language, with (F)/(M) in the labels and no gender filter", () => {
  const opts = buildVoiceOptions({
    defaultLabel: "Default (auto)", customHeader: "Custom voices (AI-generated)",
    custom: [{ id: "channarith", label: "Channarith (English) · AI-generated voice" }], groups, savedVoiceId: "",
  });
  expect(opts.map((o) => o.key)).toEqual([
    "", "hdr:custom", `${CUSTOM_PREFIX}channarith`, "hdr:en", "en-US-AvaNeural", "en-US-GuyNeural", "hdr:km", "km-KH-SreymomNeural",
  ]);
  expect(opts.filter((o) => o.header).map((o) => o.label)).toEqual(["CUSTOM VOICES (AI-GENERATED)", "EN", "KM"]);
  expect(opts.find((o) => o.key === "en-US-AvaNeural")!.label).toBe("American · American — Ava (F)");
  expect(opts.some((o) => /any|female|male/i.test(o.label) && !/\((F|M)\)/.test(o.label) && !o.header)).toBe(false);
});

test("no custom group when no voice has clips in the language", () => {
  const opts = buildVoiceOptions({ defaultLabel: "Default (auto)", customHeader: "Custom", custom: [], groups: [], savedVoiceId: "" });
  expect(opts).toEqual([{ key: "", label: "Default (auto)" }]);
});

test("clip language: Cantonese is yue, everything else its primary subtag", () => {
  expect(clipLangForLocale("zh-HK")).toBe("yue");
  expect(clipLangForLocale("yue")).toBe("yue");
  expect(clipLangForLocale("en_US")).toBe("en");
  expect(clipLangForLocale("km")).toBe("km");
});

test("custom voice label names the language and says it is AI-generated", () => {
  expect(customVoiceLabel("Wei", "yue", "en")).toMatch(/^Wei \(.+\) · AI-generated voice$/);
});
