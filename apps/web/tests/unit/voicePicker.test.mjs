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
