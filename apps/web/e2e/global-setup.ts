import { chromium, expect, type FullConfig } from "@playwright/test";
import fs from "fs";
import path from "path";
import { AUTH_STATE, BASE_URL } from "../playwright.config";

export const QA_LEARNER_EMAIL = process.env.E2E_QA_EMAIL || "qa-learner@salareen.com";
export const QA_LEARNER_PASSWORD = process.env.E2E_QA_PASSWORD || "QaTest123";

// Demo-critical backends (host ports from infra/compose/docker-compose.yml).
const SERVICES: Array<[name: string, url: string]> = [
  ["web", `${BASE_URL}/`],
  ["orchestrator", "http://localhost:8000/health"],
  ["memory", "http://localhost:8004/health"],
  ["curriculum", "http://localhost:8005/health"],
  ["identity", "http://localhost:8008/health"],
];

async function assertStackUp(): Promise<void> {
  const down: string[] = [];
  for (const [name, url] of SERVICES) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
      if (!res.ok) down.push(`${name} (${url} -> ${res.status})`);
    } catch {
      down.push(`${name} (${url} unreachable)`);
    }
  }
  if (down.length) {
    throw new Error(
      `E2E stack is not up: ${down.join(", ")}.\n` +
        "Start it first with:  make up-e2e   (from the repo root)",
    );
  }
}

export default async function globalSetup(_config: FullConfig): Promise<void> {
  // SKIP_STACK_CHECK=1 is set by the CI regression-canary job, which runs
  // source-level checks (execSync reads source files) that never need a live
  // stack. Create an empty auth state so storageState: AUTH_STATE doesn't
  // throw — tests that actually require auth will simply run unauthenticated.
  if (process.env.SKIP_STACK_CHECK) {
    fs.mkdirSync(path.dirname(AUTH_STATE), { recursive: true });
    if (!fs.existsSync(AUTH_STATE)) {
      fs.writeFileSync(AUTH_STATE, JSON.stringify({ cookies: [], origins: [] }));
    }
    return;
  }

  await assertStackUp();

  // Sign in once through the real login UI; specs reuse the storage state.
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    await page.goto(`${BASE_URL}/login`);
    await page.getByLabel(/Email/i).fill(QA_LEARNER_EMAIL);
    await page.locator('input[type="password"]').fill(QA_LEARNER_PASSWORD);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    // Login redirects to / (or /onboarding on first run); both mean the
    // token landed in localStorage.
    await page.waitForURL(/\/(onboarding)?$/, { timeout: 20_000 });
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem("aoep_token")))
      .not.toBeNull();
    // Accept the one-time post-login AI & consent disclaimer through the real
    // UI so the saved state matches a returning learner (DisclaimerGate.tsx).
    const consent = page.getByRole("button", { name: "I understand and consent" });
    if (await consent.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await consent.click();
      await expect(page.getByRole("dialog", { name: "AI and consent disclaimer" })).toBeHidden();
    }
    // Skip the one-time learning-profile survey SERVER-SIDE for every student
    // on the QA account. A local dismiss key is not enough: the component
    // re-checks identity and re-opens for any student without completed
    // onboarding (LearningProfileSurvey.tsx openForStudent), which would
    // block classroom clicks mid-spec.
    // The survey creates the identity student itself when none exists, so
    // pre-create one here and mark it skipped — otherwise the survey pops
    // for that brand-new student in the middle of a classroom spec.
    const identityUrl = process.env.E2E_IDENTITY_URL || "http://localhost:8008";
    await page.evaluate(async (idUrl) => {
      const token = localStorage.getItem("aoep_token");
      if (!token) return;
      const auth = { Authorization: `Bearer ${token}` };
      const res = await fetch(`${idUrl}/students`, { headers: auth });
      if (!res.ok) return;
      let { students } = await res.json();
      if (!students?.length) {
        const created = await fetch(`${idUrl}/students`, {
          method: "POST",
          headers: { "content-type": "application/json", ...auth },
          body: JSON.stringify({ display_name: "QA Learner", age_band: "adult", interests: [] }),
        });
        students = created.ok ? [await created.json()] : [];
      }
      for (const s of students ?? []) {
        if (!s.onboarding_completed_at) {
          await fetch(`${idUrl}/students/${s.id}/learning-profile/skip`, {
            method: "POST",
            headers: auth,
          }).catch(() => undefined);
        }
      }
    }, identityUrl);
    fs.mkdirSync(path.dirname(AUTH_STATE), { recursive: true });
    await page.context().storageState({ path: AUTH_STATE });
  } finally {
    await browser.close();
  }
}
