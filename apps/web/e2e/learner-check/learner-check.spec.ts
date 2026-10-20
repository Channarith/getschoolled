import { expect, test, type Page } from "@playwright/test";

const IDENTITY = (process.env.E2E_IDENTITY_TARGET || process.env.E2E_IDENTITY_URL || "http://localhost:8008").replace(/\/$/, "");
const PAGE_IDENTITY = /^http:\/\/(localhost|127\.0\.0\.1):8008/;

type Learner = { token: string; studentId: string };

async function newLearner(): Promise<Learner> {
  const email = `learner-check-${Date.now()}-${Math.random().toString(16).slice(2, 8)}@example.com`;
  const signup = await fetch(`${IDENTITY}/auth/signup`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password: "S3cretpass" }),
  });
  expect(signup.ok, `signup ${signup.status} ${await signup.clone().text()}`).toBe(true);
  const { token } = await signup.json();
  const auth = { Authorization: `Bearer ${token}` };
  const { students } = await (await fetch(`${IDENTITY}/students`, { headers: auth })).json();
  const studentId: string = students[0].id;
  await fetch(`${IDENTITY}/students/${studentId}/learning-profile/skip`, { method: "POST", headers: auth });
  return { token, studentId };
}

async function setupState(learner: Learner) {
  const response = await fetch(`${IDENTITY}/students/${learner.studentId}/setup-assistant`, {
    headers: { Authorization: `Bearer ${learner.token}` },
  });
  return response.json();
}

async function openLearnerCheck(page: Page, learner: Learner) {
  if (process.env.E2E_IDENTITY_TARGET) {
    await page.route(PAGE_IDENTITY, async (route) => {
      const url = route.request().url().replace(PAGE_IDENTITY, IDENTITY);
      const response = await route.fetch({ url });
      await route.fulfill({ response });
    });
  }
  await page.addInitScript(({ token, studentId }) => {
    if (sessionStorage.getItem("learner-check-seeded")) return;
    sessionStorage.setItem("learner-check-seeded", "1");
    localStorage.setItem("aoep_token", token);
    localStorage.setItem("aoep_disclaimer_accepted_v1", new Date().toISOString());
    localStorage.setItem("setup_assistant_step", "identity");
    localStorage.setItem("onboarding_student_id", studentId);
    localStorage.setItem("onboarding_learner_name", "Test Learner");
    localStorage.setItem("onboarding_age", "30");
    localStorage.setItem("onboarding_age_band", "adult");
  }, learner);
  await page.goto("/onboarding?learnerCheckMock=1");
  await expect(page.getByRole("heading", { name: "Set up your Salareen Learner Check." })).toBeVisible();
}

test("face check, voice check, then Continue to the plan step", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const learner = await newLearner();
  await openLearnerCheck(page, learner);

  await page.getByRole("button", { name: "Get started" }).click();
  await expect(page.getByTestId("learner-check-mock")).toBeVisible();
  await expect(page.getByText(/Face check · \d of 4/)).toBeVisible();

  await expect(page.getByTestId("face-status")).toHaveText("Face check: saved", { timeout: 45_000 });
  await expect(page.getByRole("button", { name: "Start voice check" })).toBeVisible();
  await page.getByRole("button", { name: "Start voice check" }).click();
  await expect(page.getByRole("button", { name: /Recording…/ })).toBeVisible();

  await expect(page.getByRole("heading", { name: "You’re all set." })).toBeVisible({ timeout: 45_000 });
  const state = await setupState(learner);
  expect(state.portrait.status).toBe("verified");
  expect(state.pose.status).toBe("verified");
  expect(state.voice.status).toBe("verified");

  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText(/Your plan/).first()).toBeVisible();
  expect((await setupState(learner)).current_step).toBe("complete");
  expect(errors).toEqual([]);
});

test("a rejected face save keeps the voice check and offers Redo face check", async ({ page }) => {
  const learner = await newLearner();
  let rejectOnce = true;
  await page.route(/\/students\/[^/]+\/biometric-face$/, async (route) => {
    if (rejectOnce) {
      rejectOnce = false;
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({ detail: "pose challenge face does not match portrait (0.05)" }),
      });
      return;
    }
    await route.fallback();
  });
  await openLearnerCheck(page, learner);

  await page.getByRole("button", { name: "Get started" }).click();
  await expect(page.getByTestId("face-status")).toHaveText("Face check: not saved", { timeout: 45_000 });
  await expect(page.getByText(/Couldn’t save your face check: 422/)).toBeVisible();

  await page.getByRole("button", { name: "Start voice check" }).click();
  await expect(page.getByTestId("voice-status")).toHaveText("Voice check: saved", { timeout: 45_000 });
  await expect(page.getByRole("heading", { name: "Voice check saved." })).toBeVisible();

  await page.getByRole("button", { name: "Redo face check" }).click();
  await expect(page.getByRole("heading", { name: "You’re all set." })).toBeVisible({ timeout: 45_000 });
  const state = await setupState(learner);
  expect(state.portrait.status).toBe("verified");
  expect(state.voice.status).toBe("verified");
});
