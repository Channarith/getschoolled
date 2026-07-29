import { expect, test } from "@playwright/test";
import { AUTH_STATE } from "../../playwright.config";

/**
 * CD-E2 — /corporate/learn locked course player: auto-start, slides,
 * grounded Q&A, and the browser-TTS path (stubbed so runs stay silent
 * and we can assert speech was requested).
 */

const LESSON_ID = "ai-fluency-essentials";

test.use({ storageState: AUTH_STATE });

test.describe("corporate locked player (CD-E2)", () => {
  test.beforeEach(async ({ page }) => {
    // Silence + record browser TTS: the player calls speechSynthesis.speak
    // for narration/answers; capture invocations instead of playing audio.
    await page.addInitScript(() => {
      const spoken: string[] = [];
      (window as unknown as { __spoken: string[] }).__spoken = spoken;
      const fake = {
        speak: (u: { text?: string }) => spoken.push(u?.text ?? ""),
        cancel: () => {},
        pause: () => {},
        resume: () => {},
        getVoices: () => [],
        speaking: false,
        pending: false,
        paused: false,
        onvoiceschanged: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => true,
      };
      Object.defineProperty(window, "speechSynthesis", { value: fake });
    });
    await page.goto(`/corporate/learn?lesson=${LESSON_ID}`);
  });

  test("locked mode auto-starts into slide 1 with corporate chrome", async ({ page }) => {
    await expect(page.getByText("← Back to Corporate training")).toBeVisible();
    // Auto-start lands on the first slide without the lesson-picker card
    // ("Start a session" only renders in unlocked /class mode).
    await expect(page.getByText(/Slide 1 of \d+/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Start a session" })).toHaveCount(0);
    await expect(
      page.getByText("AI Fluency: Essentials for the Modern Workplace"),
    ).toBeVisible();
  });

  test("slides advance and the deck has real content", async ({ page }) => {
    await expect(page.getByText(/Slide 1 of \d+/)).toBeVisible();
    const firstSlideTitle = await page.locator("h2").first().textContent();
    await page.getByRole("button", { name: "Next slide →" }).click();
    await expect(page.getByText(/Slide 2 of \d+/)).toBeVisible();
    const secondSlideTitle = await page.locator("h2").first().textContent();
    expect(secondSlideTitle?.trim()).not.toEqual(firstSlideTitle?.trim());
    // Narration line rendered for the AI teacher.
    await expect(page.getByText(/🔊 .+/)).toBeVisible();
  });

  test("Q&A returns a grounded, non-empty answer (offline-deterministic)", async ({ page }) => {
    await expect(page.getByText(/Slide 1 of \d+/)).toBeVisible();
    const question = "What is generative AI useful for at work?";
    await page.getByPlaceholder(/e\.g\./).fill(question);
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    // The learner's question shows in the transcript, followed by a
    // teacher answer. Assert shape, not exact text (offline answer is
    // grounded in retrieved passages). Use exact:true to avoid matching the
    // presenter bubble which also contains the question text as a substring.
    await expect(page.getByText(question, { exact: true })).toBeVisible();
    await expect
      .poll(
        async () => {
          const texts = await page.locator("main").innerText();
          const afterQuestion = texts.split(question).pop() ?? "";
          return afterQuestion.trim().length;
        },
        { timeout: 30_000 },
      )
      .toBeGreaterThan(40);
  });

  test("browser TTS path is exercised (speech requested for the class)", async ({ page }) => {
    await expect(page.getByText(/Slide 1 of \d+/)).toBeVisible();
    await page.getByPlaceholder(/e\.g\./).fill("Summarize this course in one sentence.");
    await page.getByRole("button", { name: "Ask", exact: true }).click();
    await expect
      .poll(async () =>
        page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.length),
        { timeout: 30_000 },
      )
      .toBeGreaterThan(0);
  });
});
