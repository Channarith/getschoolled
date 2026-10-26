import { expect, test, type Page } from "@playwright/test";

/**
 * Home page: the two front-page buttons, sign-out landing, mascot narration with pre-rendered clips, and the single
 * voice picker. Self-contained: network and audio are stubbed, so no seeded account is needed.
 */

const GROUPS = {
  groups: [{
    language: "en",
    voices: [
      { id: "en_us_f", label: "American — Aria (F)", language: "en", locale: "en-US", accent: "American", gender: "female", dialect: "" },
      { id: "en_us_ny_f", label: "New York — Aria (F)", language: "en", locale: "en-US", accent: "New York", gender: "female", dialect: "" },
      { id: "en_gb_m", label: "British — Ryan (M)", language: "en", locale: "en-GB", accent: "British", gender: "male", dialect: "" },
    ],
  }],
};

async function stubAudio(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __played: string[]; __spoken: string[] };
    w.__played = [];
    w.__spoken = [];
    class FakeAudio {
      src: string;
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(src: string) { this.src = src; }
      play() { w.__played.push(this.src); return Promise.resolve(); }
      pause() { /* stub */ }
    }
    (window as unknown as { Audio: unknown }).Audio = FakeAudio;
    const synth = window.speechSynthesis;
    if (synth) {
      synth.speak = (u: SpeechSynthesisUtterance) => { w.__spoken.push(u.text); };
      synth.cancel = () => { /* stub */ };
    }
  });
}

const signedIn = (page: Page) =>
  page.addInitScript(() => {
    localStorage.setItem("aoep_token", "e2e-token");
    localStorage.setItem("aoep_signed_in", "1");
    localStorage.setItem("aoep_disclaimer_accepted_v1", new Date().toISOString());   // skip the one-time consent dialog
  });

test.describe("front page buttons", () => {
  test("signed out: the simple page has exactly two buttons, Try the demo and Log in", async ({ page }) => {
    await page.goto("/");
    const cta = page.getByTestId("landing-guest-cta");
    await expect(cta.getByRole("link", { name: /try the demo/i })).toHaveAttribute("href", "/demo");
    await expect(cta.getByRole("link", { name: /^log in$/i })).toHaveAttribute("href", "/login");
    await expect(cta.getByRole("link")).toHaveCount(2);
    await expect(page.getByTestId("feature-tutor")).toHaveCount(0);   // the orbital hero is for signed-in visitors
  });

  test("signed in: the two buttons are hidden", async ({ page }) => {
    await signedIn(page);
    await page.goto("/");
    await expect(page.getByTestId("feature-tutor")).toBeVisible();
    await expect(page.getByTestId("landing-guest-cta")).toHaveCount(0);
  });

  test("signing out lands on / with both buttons", async ({ page }) => {
    await signedIn(page);
    await page.route("**/auth/logout", (r) => r.fulfill({ status: 200, body: "{}" }));
    await page.goto("/");
    await expect(page.getByTestId("landing-guest-cta")).toHaveCount(0);
    await page.getByRole("button", { name: /profile|account|menu/i }).first().click();
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByTestId("landing-guest-cta").getByRole("link", { name: /^log in$/i })).toBeVisible();
    await expect(page.getByTestId("landing-guest-cta").getByRole("link", { name: /try the demo/i })).toBeVisible();
  });
});

test.describe("mascot narration", () => {
  test("clicking a card plays the pre-rendered Salane clip, not the browser voice", async ({ page }) => {
    await stubAudio(page);
    await signedIn(page);
    await page.goto("/");
    await page.getByTestId("feature-tutor").click();
    await expect.poll(() => page.evaluate(() => (window as unknown as { __played: string[] }).__played.length)).toBe(1);
    const played = await page.evaluate(() => (window as unknown as { __played: string[] }).__played[0]);
    expect(played).toMatch(/^\/landing-voice\/salane\/en\/[0-9a-f]{14}\.mp3$/);
    expect(await page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.length)).toBe(0);
    const res = await page.request.get(played);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("audio");
  });

  test("hovering before any click stays silent (no autoplay)", async ({ page }) => {
    await stubAudio(page);
    await signedIn(page);
    await page.goto("/");
    await page.getByTestId("feature-play").hover();
    await page.waitForTimeout(700);
    expect(await page.evaluate(() => (window as unknown as { __played: string[] }).__played.length)).toBe(0);
    expect(await page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.length)).toBe(0);
  });

  test("missing clip falls back to the browser voice", async ({ page }) => {
    await stubAudio(page);
    await signedIn(page);
    await page.route("**/landing-voice/salane/index.json", (r) => r.fulfill({ status: 404, body: "" }));
    await page.goto("/");
    await page.getByTestId("feature-live").click();
    await expect.poll(() => page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.length)).toBe(1);
    expect(await page.evaluate(() => (window as unknown as { __played: string[] }).__played.length)).toBe(0);
  });

  test("a chosen consented voice plays its own clip for the line", async ({ page }) => {
    await stubAudio(page);
    await signedIn(page);
    const index = await (await page.request.get("/landing-voice/salane/index.json")).json();
    const hash = index.clips.en[0];
    await page.route("**/voice-assets/voices.json", (r) => r.fulfill({ json: { voices: [{ id: "channarith", label: "Channarith", ai_label: "AI-generated voice of Channarith", active: true }] } }));
    await page.route("**/voice-assets/channarith/index.json", (r) => r.fulfill({ json: { ext: "mp3", clips: { en: [hash] } } }));
    await page.addInitScript(() => localStorage.setItem("aoep_demo_voice", "channarith"));
    await page.goto("/");
    // Every card line has its own hash; click each until the custom clip is the one played.
    for (const id of ["tutor", "play", "live"]) {
      await page.getByTestId(`feature-${id}`).click();
      await page.waitForTimeout(300);
    }
    const played = await page.evaluate(() => (window as unknown as { __played: string[] }).__played);
    expect(played.some((u) => u.includes("/voice-assets/channarith/en/"))).toBe(true);
    expect(played.some((u) => u.startsWith("/landing-voice/salane/en/"))).toBe(true);
  });
});

test.describe("voice picker", () => {
  test("one dropdown: no gender filter, duplicates removed, custom voice group on top", async ({ page }) => {
    await signedIn(page);
    await page.route("**/tts/voices", (r) => r.fulfill({ json: GROUPS }));
    await page.route("**/voice-assets/voices.json", (r) => r.fulfill({ json: { voices: [
      { id: "channarith", label: "Channarith", ai_label: "AI", active: true },
      { id: "wei", label: "Wei", ai_label: "AI", active: true },
    ] } }));
    await page.route("**/voice-assets/channarith/index.json", (r) => r.fulfill({ json: { ext: "mp3", clips: { en: ["a"] } } }));
    await page.route("**/voice-assets/wei/index.json", (r) => r.fulfill({ json: { ext: "mp3", clips: { yue: ["b"] } } }));
    await page.goto("/");
    await page.getByRole("button", { name: /profile|account|menu/i }).first().click();
    const select = page.getByRole("combobox", { name: /voice/i });
    await expect(select).toBeVisible();
    await expect(page.getByRole("button", { name: /^(any|female|male)$/i })).toHaveCount(0);
    const options = await select.locator("option").allTextContents();
    expect(options.some((o) => /Channarith · /.test(o))).toBe(true);
    expect(options.some((o) => /^Wei/.test(o))).toBe(false);          // no Cantonese clips for the English site
    expect(options.filter((o) => /Aria/.test(o))).toHaveLength(1);    // New York — Aria is the same audio voice
    expect(options.some((o) => /Ryan \(M\)/.test(o))).toBe(true);     // (F)/(M) markers stay
    await select.selectOption({ label: options.find((o) => /Channarith/.test(o))! });
    expect(await page.evaluate(() => localStorage.getItem("aoep_demo_voice"))).toBe("channarith");
  });
});
