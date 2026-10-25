import type { VoiceGroup } from "../api";
import { AUTO_PREFIX, CUSTOM_PREFIX, buildVoiceGroups, clipLangForLocale, customVoiceLabel, distinctVoiceGroups, filterVoiceGroups, flattenVoiceGroups, selectedVoiceKey } from "../voicePicker";

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

const CLONES = [
  { id: "channarith", label: "Channarith (English)", primary_lang: "en", active: true },
  { id: "wei", label: "Wei (Cantonese)", primary_lang: "yue", active: true },
  { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", primary_lang: "en", active: true, default: true, kind: "stock" },
];
const cantonese: VoiceGroup = { language: "zh", voices: [v("zh-HK-HiuMaanNeural", "zh-HK", "Cantonese", "Cantonese — HiuMaan (F)", "female")] };

test("voices are grouped by language, English first, each group opens with its Salane Voice, and there is no gender filter", () => {
  const out = buildVoiceGroups({ groups: [...groups, cantonese], clones: CLONES, salaneLabel: "Salane Voice (Sage)", hasDefault: true, nativeNames: { km: "ខ្មែរ", yue: "粵語", en: "English" } });
  expect(out[0].key).toBe("en");
  expect(out.map((g) => g.label)).toEqual(expect.arrayContaining(["English", "ខ្មែរ", "粵語"]));
  expect(out[0].options.map((o) => o.key)).toEqual([`${AUTO_PREFIX}en`, `${CUSTOM_PREFIX}channarith`, "en-US-AvaNeural", "en-US-GuyNeural"]);
  expect(out[0].options[0].label).toBe("Salane Voice (Sage)");
  expect(out.find((g) => g.key === "yue")!.options.map((o) => o.key)).toEqual([`${AUTO_PREFIX}yue`, `${CUSTOM_PREFIX}wei`, "zh-HK-HiuMaanNeural"]);
  expect(out.find((g) => g.key === "km")!.options[0].label).toBe("Salane Voice (default)");
  const rows = flattenVoiceGroups(out);
  expect(rows.filter((r) => r.header).length).toBe(out.length);
  expect(rows.find((r) => r.key === "en-US-AvaNeural")!.label).toBe("American · American — Ava (F)");
  expect(rows.some((r) => !r.header && /^(any|female|male)$/i.test(r.label))).toBe(false);
});

test("offline: English still carries the Salane Voice", () => {
  const out = buildVoiceGroups({ groups: [], clones: [], hasDefault: false });
  expect(out.map((g) => g.key)).toEqual(["en"]);
  expect(out[0].options).toEqual([{ key: `${AUTO_PREFIX}en`, label: "Salane Voice (default)", locale: "en" }]);
});

test("search matches the option, the language's names and the locale code, and the selected option stays", () => {
  const out = buildVoiceGroups({ groups: [...groups, cantonese], clones: CLONES, hasDefault: true, nativeNames: { km: "ខ្មែរ", yue: "粵語" } });
  expect(filterVoiceGroups(out, "khmer").map((g) => g.key)).toEqual(["km"]);
  expect(filterVoiceGroups(out, "ខ្មែរ").map((g) => g.key)).toEqual(["km"]);
  expect(filterVoiceGroups(out, "cantonese").map((g) => g.key)).toContain("yue");
  expect(filterVoiceGroups(out, "zh-hk").map((g) => g.key)).toContain("yue");
  const kept = filterVoiceGroups(out, "ava", "km-KH-SreymomNeural").flatMap((g) => g.options.map((o) => o.key));
  expect(kept).toEqual(expect.arrayContaining(["en-US-AvaNeural", "km-KH-SreymomNeural"]));
  expect(filterVoiceGroups(out, "qqqqqq")).toEqual([]);
  expect(filterVoiceGroups(out, "  ")).toBe(out);
});

test("the selected option: the picked company voice, else a deliberate catalog voice, else the Salane Voice of the app's language", () => {
  const out = buildVoiceGroups({ groups: [...groups, cantonese], clones: CLONES, hasDefault: true });
  const k = (o: object) => selectedVoiceKey({ cloneId: "", cloneListed: false, savedVoiceId: "", locale: "en", groups: out, ...o });
  expect(k({})).toBe(`${AUTO_PREFIX}en`);
  expect(k({ locale: "yue" })).toBe(`${AUTO_PREFIX}yue`);
  expect(k({ locale: "th" })).toBe(`${AUTO_PREFIX}en`);
  expect(k({ savedVoiceId: "km-KH-SreymomNeural" })).toBe("km-KH-SreymomNeural");
  expect(k({ cloneId: "wei", cloneListed: true })).toBe(`${CUSTOM_PREFIX}wei`);
  expect(k({ cloneId: "wei", cloneListed: false })).toBe(`${AUTO_PREFIX}en`);
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
