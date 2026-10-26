// The ONE voice-and-language control: no separate Language section in the account menu or the footer, voices grouped by language with a
// search box, "Sage · English" first, and picking a voice sets the app language (html lang, direction, stored locale).
// Also the start-up rules: nothing stored -> the browser's language with its Salane Voice; an old stored language and the old automatic
// voice keep working. Needs `next dev` (or a build) running; the speech catalog and the published voices are stubbed.
//   node apps/web/e2e/voice-language-picker.mjs http://localhost:3127
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const pw = require("playwright");
const BASE = process.argv[2] || "http://localhost:3127";

const v = (id, label, locale, accent, gender = "female") => ({ id, label, language: locale.split("-")[0], locale, accent, gender, dialect: "" });
const catalog = JSON.stringify({ groups: [
  { language: "en", voices: [v("en_us_f", "American — Aria (F)", "en-US", "American"), v("en_gb_f", "British — Sonia (F)", "en-GB", "British")] },
  { language: "es", voices: [v("es_es_f", "Spanish (Spain) — Elvira (F)", "es-ES", "Spanish (Spain)")] },
  { language: "km", voices: [v("km_kh_f", "Khmer — Sreymom (F)", "km-KH", "Khmer")] },
  { language: "ar", voices: [v("ar_eg_f", "Egyptian — Salma (F)", "ar-EG", "Egyptian")] },
  { language: "zh", voices: [v("zh_cn_f", "Beijing — Xiaoxiao (F)", "zh-CN", "Beijing"), v("zh_hk_f", "Cantonese — HiuMaan (F)", "zh-HK", "Cantonese")] },
] });
const voices = JSON.stringify({ voices: [
  { id: "channarith", label: "Channarith (English)", name: "Channarith", ai_label: "AI-generated voice of Channarith", active: true, gender: "male", primary_lang: "en" },
  { id: "wei", label: "Wei (Cantonese)", name: "Wei", ai_label: "AI-generated voice of Wei", active: true, gender: "female", primary_lang: "yue" },
  { id: "stock-f-young-warm", label: "Sage (designed)", name: "Sage", kind: "stock", ai_label: "AI-generated voice (designed with VoxCPM2)", active: true, default: true, gender: "female", primary_lang: "en" },
] });

const b = await pw.chromium.launch();
const errors = [];

async function open(ctxOptions = {}, store = {}) {
  const ctx = await b.newContext({ viewport: { width: 1300, height: 1000 }, ...ctxOptions });
  await ctx.addInitScript((s) => { for (const [k, val] of Object.entries(s)) if (localStorage.getItem(k) === null) localStorage.setItem(k, val); }, store);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
  await page.route("**/tts/voices", (r) => r.fulfill({ status: 200, contentType: "application/json", body: catalog }));
  await page.route("**/voice-assets/voices.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: voices }));
  await page.route("**/voice-assets/*/index.json", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ext: "mp3", clips: {} }) }));
  await page.route("**/tts", (r) => r.fulfill({ status: 501, body: "" }));
  await page.goto(`${BASE}/report-bug`, { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.waitForTimeout(3000);
  await page.locator('button[aria-haspopup="menu"]').first().click({ timeout: 15000 });   // the profile button; its label is localized, so no name match
  await page.waitForTimeout(1500);
  return { ctx, page };
}
const lang = (page) => page.evaluate(() => document.documentElement.lang);
const dir = (page) => page.evaluate(() => document.documentElement.dir);
const stored = (page, k) => page.evaluate((key) => localStorage.getItem(key), k);

// 1. one control: no Language section in the menu, no Language selector in the footer
{
  const { ctx, page } = await open({ locale: "en-US" });
  assert.equal(await page.getByText("🌐").count(), 0, "the menu has no separate Language section");
  assert.equal(await page.locator("footer select").count(), 0, "the footer has no Language selector");
  const sel = page.getByLabel(/voice/i).first();
  const voiceSel = page.locator("select").filter({ has: page.locator("option", { hasText: "Sage · English" }) }).first();
  assert.ok(await voiceSel.isVisible());
  assert.equal(await voiceSel.inputValue(), "auto:en", "a visitor who never chose sees Sage");
  const groups = await voiceSel.locator("optgroup").evaluateAll((els) => els.map((e) => e.label));
  assert.equal(groups[0], "English", "English first");
  for (const name of ["Español", "ខ្មែរ", "粵語"]) assert.ok(groups.includes(name), `group ${name} (the language's own name)`);
  assert.equal(await page.getByRole("searchbox").count() + await page.locator("input[type=search]").count() > 0, true);

  // 2. search
  await page.locator("input[type=search]").first().fill("khmer");
  assert.deepEqual(await voiceSel.locator("optgroup").evaluateAll((els) => els.map((e) => e.label)).then((g) => g.filter((x) => x !== "English")), ["ខ្មែរ"]);
  await page.locator("input[type=search]").first().fill("");

  // 3. picking a voice sets the language
  await voiceSel.selectOption("km_kh_f");
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "km"); assert.equal(await stored(page, "aiclassroom.locale.v1"), "km");
  assert.equal(await stored(page, "aoep_voice_explicit"), "1");
  await voiceSel.selectOption("ar_eg_f");
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "ar"); assert.equal(await dir(page), "rtl", "direction follows the language");
  await voiceSel.selectOption("clone:wei");   // the Cantonese company voice
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "yue"); assert.equal(await stored(page, "aoep_demo_voice"), "wei");
  await voiceSel.selectOption("clone:channarith");   // English company voice
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "en"); assert.equal(await dir(page), "ltr");
  await voiceSel.selectOption("en_gb_f");
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "en-GB", "an accent voice keeps the accent");
  await voiceSel.selectOption("auto:en");   // Sage on purpose
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "en-GB", "Sage is English: the UK visitor keeps en-GB");
  assert.equal(await stored(page, "aoep_voice_explicit"), "0"); assert.equal(await stored(page, "aoep_demo_voice"), "default");
  await voiceSel.selectOption("es_es_f");
  await page.waitForTimeout(600);
  assert.equal(await lang(page), "es", "the Spanish voice sets Spanish");
  await ctx.close();
}

// 4. start-up: the browser's language when nothing is stored; the Spanish visitor sees the Spanish voice
{
  const { ctx, page } = await open({ locale: "es-ES" });
  assert.equal(await lang(page), "es");
  const voiceSel = page.locator("select").filter({ has: page.locator("option", { hasText: "Sage · English" }) }).first();
  assert.equal(await voiceSel.inputValue(), "es_es_f");
  await ctx.close();
}

// 5. migration: only a language stored (older release) keeps the language; the old automatic voice resolves to the default
{
  const { ctx, page } = await open({ locale: "en-US" }, { "aiclassroom.locale.v1": "fr", aoep_demo_voice: "default" });
  assert.equal(await lang(page), "fr", "a stored language is kept");
  await ctx.close();
}
// ... and a stored deliberate voice wins over the stored language
{
  const { ctx, page } = await open({ locale: "en-US" }, { "aiclassroom.locale.v1": "en", aoep_drive_voice: "km-KH-SreymomNeural", aoep_voice_explicit: "1" });
  assert.equal(await lang(page), "km", "the language follows a stored voice");
  await ctx.close();
}
// ... an accent voice the app wrote itself is not a choice: en-GB stays and Sage is still the default
{
  const { ctx, page } = await open({ locale: "en-GB" }, { aoep_drive_voice: "en_gb_f" });
  assert.equal(await lang(page), "en-GB");
  const voiceSel = page.locator("select").filter({ has: page.locator("option", { hasText: "Sage · English" }) }).first();
  assert.equal(await voiceSel.inputValue(), "auto:en");
  await ctx.close();
}

assert.deepEqual(errors, []);
console.log("voice language picker: ok");
await b.close();
