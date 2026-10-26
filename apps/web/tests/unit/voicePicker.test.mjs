import test from "node:test";
import assert from "node:assert/strict";

import { clipLangForLocale, customVoiceLabel, distinctVoiceGroups } from "../../app/lib/voicePicker.ts";

const v = (id, label, locale, gender = "female") => ({ id, label, language: locale.split("-")[0], locale, accent: label.split("—")[0].trim(), gender, dialect: "" });
const groups = [{
  language: "en",
  voices: [
    v("en_us_f", "American — Aria (F)", "en-US"),
    v("en_us_ny_f", "New York — Aria (F)", "en-US"),
    v("en_us_m", "American — Guy (M)", "en-US", "male"),
    v("en_us_ny_m", "New York — Guy (M)", "en-US", "male"),
    v("en_gb_f", "British — Sonia (F)", "en-GB"),
  ],
}];

test("each audio voice is listed once", () => {
  const ids = distinctVoiceGroups(groups)[0].voices.map((x) => x.id);
  assert.deepEqual(ids, ["en_us_f", "en_us_m", "en_gb_f"]);
});

test("a duplicate the visitor already saved stays listed, so their choice never disappears", () => {
  const ids = distinctVoiceGroups(groups, "en_us_ny_f")[0].voices.map((x) => x.id);
  assert.ok(ids.includes("en_us_ny_f"));
  assert.equal(ids.filter((id) => id === "en_us_f").length <= 1, true);
});

test("clip language for a UI locale", () => {
  assert.equal(clipLangForLocale("en-GB"), "en");
  assert.equal(clipLangForLocale("zh-HK"), "yue");
  assert.equal(clipLangForLocale("yue"), "yue");
  assert.equal(clipLangForLocale("zh-CN"), "zh");
  assert.equal(clipLangForLocale(""), "en");
});

test("custom voice label carries the consent name, language and the AI badge", () => {
  const label = customVoiceLabel("Wei", "yue", "en");
  assert.match(label, /^Wei \(.+\) · AI-generated voice$/);
  assert.match(label, /Cantonese/);
});

// ---- one list grouped by language, with search ---------------------------------------------------------------------------------
import { AUTO_PREFIX, CUSTOM_PREFIX, buildVoiceOptions, filterVoiceOptions, nativeLanguageName, selectedVoiceValue } from "../../app/lib/voicePicker.ts";

const cat = (id, label, locale, accent) => ({ id, label, language: locale.split("-")[0], locale, accent, gender: "female", dialect: "" });
const CATALOG = [
  { language: "en", voices: [cat("en-US-AriaNeural", "American — Aria (F)", "en-US", "American"), cat("en-GB-SoniaNeural", "British — Sonia (F)", "en-GB", "British")] },
  { language: "es", voices: [cat("es-MX-DaliaNeural", "Mexican — Dalia (F)", "es-MX", "Mexican")] },
  { language: "zh", voices: [cat("zh-CN-XiaoxiaoNeural", "Beijing — Xiaoxiao (F)", "zh-CN", "Beijing"), cat("zh-HK-HiuMaanNeural", "Cantonese — HiuMaan (F)", "zh-HK", "Cantonese")] },
  { language: "km", voices: [cat("km-KH-SreymomNeural", "Khmer — Sreymom (F)", "km-KH", "Khmer")] },
];
const CLONES = [
  { id: "channarith", label: "Channarith (English)", primary_lang: "en", active: true },
  { id: "wei", label: "Wei (Cantonese)", primary_lang: "yue", active: true },
  { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", primary_lang: "en", active: true, default: true, kind: "stock" },
];

test("voices are grouped by the language they speak, and English opens with Sage", () => {
  const groups = buildVoiceOptions({ groups: CATALOG, clones: CLONES, salaneLabel: "Salane Voice (Sage)", hasDefault: true });
  assert.equal(groups[0].key, "en");
  assert.deepEqual(groups.map((g) => g.key).sort(), ["en", "es", "km", "yue", "zh"]);
  const en = groups[0].options;
  assert.equal(en[0].value, `${AUTO_PREFIX}en`);
  assert.match(en[0].label, /^Sage · /);
  assert.ok(en.some((o) => o.value === `${CUSTOM_PREFIX}channarith` && /Channarith · /.test(o.label)));
  assert.ok(!en.some((o) => o.value === `${CUSTOM_PREFIX}stock-f-young-warm`), "Sage is the English group's first entry, not a second copy");
  const yue = groups.find((g) => g.key === "yue");
  assert.deepEqual(yue.options.map((o) => o.value), [`${CUSTOM_PREFIX}wei`, "zh-HK-HiuMaanNeural"], "Cantonese voices, with no language-only row");
  assert.ok(!groups.find((g) => g.key === "zh").options.some((o) => o.value === "zh-HK-HiuMaanNeural"));
  assert.match(groups.find((g) => g.key === "es").options[0].label, /Dalia \(F\) · /);
  assert.equal(groups.find((g) => g.key === "km").label, "ខ្មែរ", "headers use the language's own name");
  assert.ok(!groups.some((g) => g.key !== "en" && g.options.some((o) => o.value.startsWith(AUTO_PREFIX))));
});

test("offline: English still carries the Salane Voice, and nothing breaks without a catalog", () => {
  const groups = buildVoiceOptions({ groups: [], clones: [], hasDefault: false });
  assert.deepEqual(groups.map((g) => g.key), ["en"]);
  assert.match(groups[0].options[0].label, /Salane Voice · /);
});

test("search matches the option, the language's own name, its English name and the locale code, and keeps the selected option", () => {
  const groups = buildVoiceOptions({ groups: CATALOG, clones: CLONES, salaneLabel: "Salane Voice (Sage)", hasDefault: true });
  const keys = (q, keep = "") => filterVoiceOptions(groups, q, keep).map((g) => g.key);
  assert.deepEqual(keys("khmer"), ["km"]);
  assert.deepEqual(keys("ខ្មែរ"), ["km"]);
  assert.deepEqual(keys("espanol"), ["es"], "diacritics do not matter");
  assert.ok(keys("cantonese").includes("yue"), "the English name of the language finds its group");
  assert.ok(keys("zh-hk").includes("yue"), "the locale code finds the Cantonese voice");
  assert.deepEqual(keys("sonia"), ["en"]);
  const kept = filterVoiceOptions(groups, "sonia", "km-KH-SreymomNeural").flatMap((g) => g.options.map((o) => o.value));
  assert.ok(kept.includes("km-KH-SreymomNeural") && kept.includes("en-GB-SoniaNeural"));
  assert.equal(filterVoiceOptions(groups, "   ").length, groups.length);
  assert.equal(filterVoiceOptions(groups, "qqqqqq").length, 0);
});

test("the select shows the picked voice, else the first voice of that language, else Sage", () => {
  const groups = buildVoiceOptions({ groups: CATALOG, clones: CLONES, salaneLabel: "Salane Voice (Sage)", hasDefault: true });
  const v = (o) => selectedVoiceValue({ cloneId: "", cloneListed: false, savedVoiceId: "", locale: "en", groups, ...o });
  assert.equal(v({}), `${AUTO_PREFIX}en`);
  assert.equal(v({ locale: "es" }), "es-MX-DaliaNeural");
  assert.equal(v({ locale: "en-GB" }), `${AUTO_PREFIX}en`);
  assert.equal(v({ locale: "yue" }), `${CUSTOM_PREFIX}wei`);
  assert.equal(v({ locale: "th" }), `${AUTO_PREFIX}en`, "a language with no voice shows Sage");
  assert.equal(v({ savedVoiceId: "km-KH-SreymomNeural" }), "km-KH-SreymomNeural");
  assert.equal(v({ cloneId: "wei", cloneListed: true, savedVoiceId: "km-KH-SreymomNeural" }), `${CUSTOM_PREFIX}wei`);
  assert.equal(v({ cloneId: "wei", cloneListed: false }), `${AUTO_PREFIX}en`, "a withdrawn voice falls back to Sage");
});

test("native language names", () => {
  assert.equal(nativeLanguageName("es"), "Español");
  assert.equal(nativeLanguageName("km"), "ខ្មែរ");
  assert.equal(nativeLanguageName("yue"), "粵語");
});

test("the app's own language names win over what the browser can name", () => {
  const groups = buildVoiceOptions({ groups: CATALOG, clones: CLONES, hasDefault: true, nativeNames: { km: "ខ្មែរ", yue: "粵語", en: "English" } });
  assert.equal(groups.find((g) => g.key === "km").label, "ខ្មែរ");
  assert.equal(groups.find((g) => g.key === "yue").label, "粵語");
});
